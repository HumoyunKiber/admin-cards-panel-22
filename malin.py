#!/usr/bin/env python3
"""
Complete SimCard Management API Server
SQLite database with FastAPI + External API Integration
Port: 9022
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sqlite3
import uvicorn
from datetime import datetime, timedelta
import uuid
import json
import httpx
import asyncio
import logging

# Configure logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SimCard Management API", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_NAME = "simcard_db.sqlite"

# External API configuration
EXTERNAL_API_BASE_URL = "http://localhost:9020"  # SimCard status API
EXTERNAL_API_TIMEOUT = 10.0

def init_database():
    """Initialize SQLite database with tables"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Shops table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shops (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            ownerName TEXT NOT NULL,
            ownerPhone TEXT NOT NULL,
            address TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            status TEXT NOT NULL DEFAULT 'active',
            region TEXT NOT NULL,
            assignedSimCards TEXT DEFAULT '[]',
            addedDate TEXT NOT NULL
        )
    """)
    
    # SimCards table - Enhanced with more fields
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS simcards (
            id TEXT PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'available',
            assignedTo TEXT,
            assignedShopName TEXT,
            addedDate TEXT NOT NULL,
            saleDate TEXT,
            lastChecked TEXT,
            lastExternalCheck TEXT,
            externalStatus TEXT,
            checkHistory TEXT DEFAULT '[]'
        )
    """)
    
    # Users table (for auth)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'admin'
        )
    """)
    
    # Status check logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS status_check_logs (
            id TEXT PRIMARY KEY,
            simcard_id TEXT,
            simcard_code TEXT,
            old_status TEXT,
            new_status TEXT,
            source TEXT,
            timestamp TEXT,
            details TEXT
        )
    """)
    
    # Insert default admin user (only if doesn't exist)
    cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, password, role)
        VALUES (?, ?, ?, ?)
    """, (str(uuid.uuid4()), "admin", "admin123", "admin"))
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully!")

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

async def check_external_simcard_status(simcard_code: str) -> Dict[str, Any]:
    """Check simcard status from external API"""
    try:
        async with httpx.AsyncClient(timeout=EXTERNAL_API_TIMEOUT) as client:
            response = await client.post(
                f"{EXTERNAL_API_BASE_URL}/check-simcard-status",
                json={"code": simcard_code}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"External API returned status {response.status_code} for {simcard_code}")
                return {
                    "status": "error",
                    "is_sold": False,
                    "sale_date": None,
                    "message": f"API error: {response.status_code}"
                }
    except Exception as e:
        logger.error(f"Error checking external API for {simcard_code}: {str(e)}")
        return {
            "status": "error",
            "is_sold": False,
            "sale_date": None,
            "message": f"Connection error: {str(e)}"
        }

async def update_simcard_from_external_data(db, simcard_id: str, simcard_code: str, external_data: Dict[str, Any]):
    """Update simcard in database based on external API response"""
    cursor = db.cursor()
    
    # Get current simcard data
    cursor.execute("SELECT * FROM simcards WHERE id = ?", (simcard_id,))
    current_simcard = cursor.fetchone()
    
    if not current_simcard:
        return False
    
    current_status = current_simcard["status"]
    new_status = current_status
    sale_date = current_simcard["saleDate"]
    
    # Update status based on external API response
    if external_data.get("is_sold", False):
        new_status = "sold"
        if not sale_date and external_data.get("sale_date"):
            sale_date = external_data["sale_date"]
        elif not sale_date:
            sale_date = datetime.now().isoformat()
    
    # Prepare check history
    check_history = json.loads(current_simcard["checkHistory"] or "[]")
    check_history.append({
        "timestamp": datetime.now().isoformat(),
        "external_status": external_data.get("status"),
        "is_sold": external_data.get("is_sold", False),
        "message": external_data.get("message", "")
    })
    
    # Keep only last 10 history entries
    if len(check_history) > 10:
        check_history = check_history[-10:]
    
    # Update simcard
    cursor.execute("""
        UPDATE simcards 
        SET status = ?, saleDate = ?, lastChecked = ?, lastExternalCheck = ?, 
            externalStatus = ?, checkHistory = ?
        WHERE id = ?
    """, (
        new_status,
        sale_date,
        datetime.now().isoformat(),
        datetime.now().isoformat(),
        external_data.get("status"),
        json.dumps(check_history),
        simcard_id
    ))
    
    # Log status change if status changed
    if current_status != new_status:
        cursor.execute("""
            INSERT INTO status_check_logs 
            (id, simcard_id, simcard_code, old_status, new_status, source, timestamp, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            simcard_id,
            simcard_code,
            current_status,
            new_status,
            "external_api",
            datetime.now().isoformat(),
            json.dumps(external_data)
        ))
        
        logger.info(f"SimCard {simcard_code} status changed from {current_status} to {new_status}")
    
    db.commit()
    return True

# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str

class ShopCreate(BaseModel):
    name: str
    ownerName: str
    ownerPhone: str
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    region: str

class ShopUpdate(BaseModel):
    name: Optional[str] = None
    ownerName: Optional[str] = None
    ownerPhone: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None
    region: Optional[str] = None

class SimCardCreate(BaseModel):
    code: str

class SimCardUpdate(BaseModel):
    code: Optional[str] = None
    status: Optional[str] = None
    assignedTo: Optional[str] = None
    assignedShopName: Optional[str] = None

class AssignSimCardsRequest(BaseModel):
    shopId: str
    count: int

class BulkSimCardCreate(BaseModel):
    codes: List[str]

# Auth endpoints
@app.post("/auth/login")
async def login(request: LoginRequest, db = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", 
                   (request.username, request.password))
    user = cursor.fetchone()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "success": True,
        "token": "test-token-123",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"]
        }
    }

@app.post("/auth/logout")
async def logout():
    return {"success": True}

# Shop endpoints
@app.get("/shops")
async def get_shops(db = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM shops ORDER BY addedDate DESC")
    shops = cursor.fetchall()
    
    result = []
    for shop in shops:
        shop_dict = dict(shop)
        shop_dict["assignedSimCards"] = json.loads(shop_dict["assignedSimCards"])
        result.append(shop_dict)
    
    return result

@app.post("/shops")
async def create_shop(shop: ShopCreate, db = Depends(get_db)):
    shop_id = str(uuid.uuid4())
    cursor = db.cursor()
    
    cursor.execute("""
        INSERT INTO shops 
        (id, name, ownerName, ownerPhone, address, latitude, longitude, status, region, assignedSimCards, addedDate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (shop_id, shop.name, shop.ownerName, shop.ownerPhone, shop.address,
          shop.latitude, shop.longitude, "active", shop.region, "[]", datetime.now().isoformat()))
    
    db.commit()
    
    # Return created shop
    cursor.execute("SELECT * FROM shops WHERE id = ?", (shop_id,))
    created_shop = cursor.fetchone()
    shop_dict = dict(created_shop)
    shop_dict["assignedSimCards"] = json.loads(shop_dict["assignedSimCards"])
    
    return shop_dict

@app.put("/shops/{shop_id}")
async def update_shop(shop_id: str, shop: ShopUpdate, db = Depends(get_db)):
    cursor = db.cursor()
    
    # Check if shop exists
    cursor.execute("SELECT * FROM shops WHERE id = ?", (shop_id,))
    existing_shop = cursor.fetchone()
    if not existing_shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Build update query dynamically
    update_fields = {}
    if shop.name is not None:
        update_fields["name"] = shop.name
    if shop.ownerName is not None:
        update_fields["ownerName"] = shop.ownerName
    if shop.ownerPhone is not None:
        update_fields["ownerPhone"] = shop.ownerPhone
    if shop.address is not None:
        update_fields["address"] = shop.address
    if shop.latitude is not None:
        update_fields["latitude"] = shop.latitude
    if shop.longitude is not None:
        update_fields["longitude"] = shop.longitude
    if shop.status is not None:
        update_fields["status"] = shop.status
    if shop.region is not None:
        update_fields["region"] = shop.region
    
    if update_fields:
        set_clause = ", ".join([f"{key} = ?" for key in update_fields.keys()])
        values = list(update_fields.values()) + [shop_id]
        cursor.execute(f"UPDATE shops SET {set_clause} WHERE id = ?", values)
        db.commit()
    
    # Return updated shop
    cursor.execute("SELECT * FROM shops WHERE id = ?", (shop_id,))
    updated_shop = cursor.fetchone()
    shop_dict = dict(updated_shop)
    shop_dict["assignedSimCards"] = json.loads(shop_dict["assignedSimCards"])
    
    return shop_dict

@app.delete("/shops/{shop_id}")
async def delete_shop(shop_id: str, db = Depends(get_db)):
    cursor = db.cursor()
    
    # Check if shop exists
    cursor.execute("SELECT * FROM shops WHERE id = ?", (shop_id,))
    shop = cursor.fetchone()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Delete shop
    cursor.execute("DELETE FROM shops WHERE id = ?", (shop_id,))
    
    # Update assigned simcards
    cursor.execute("UPDATE simcards SET status = 'available', assignedTo = NULL, assignedShopName = NULL WHERE assignedTo = ?", (shop_id,))
    
    db.commit()
    return {"success": True}

@app.get("/shops/{shop_id}/stats")
async def get_shop_stats(shop_id: str, db = Depends(get_db)):
    cursor = db.cursor()
    
    # Check if shop exists
    cursor.execute("SELECT * FROM shops WHERE id = ?", (shop_id,))
    shop = cursor.fetchone()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Get simcard stats for this shop
    cursor.execute("SELECT status, COUNT(*) as count FROM simcards WHERE assignedTo = ? GROUP BY status", (shop_id,))
    stats = cursor.fetchall()
    
    result = {
        "shopId": shop_id,
        "shopName": shop["name"],
        "assigned": 0,
        "sold": 0,
        "total": 0
    }
    
    for stat in stats:
        if stat["status"] == "assigned":
            result["assigned"] = stat["count"]
        elif stat["status"] == "sold":
            result["sold"] = stat["count"]
        result["total"] += stat["count"]
    
    return result

# SimCard endpoints
@app.get("/simcards")
async def get_simcards(db = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM simcards ORDER BY addedDate DESC")
    simcards = cursor.fetchall()
    
    result = []
    for simcard in simcards:
        simcard_dict = dict(simcard)
        # Parse check history if exists
        try:
            simcard_dict["checkHistory"] = json.loads(simcard_dict["checkHistory"] or "[]")  
        except:
            simcard_dict["checkHistory"] = []
        result.append(simcard_dict)
    
    return result

@app.post("/simcards")
async def create_simcard(simcard: SimCardCreate, db = Depends(get_db)):
    simcard_id = str(uuid.uuid4())
    cursor = db.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO simcards 
            (id, code, status, assignedTo, assignedShopName, addedDate, saleDate, lastChecked, lastExternalCheck, externalStatus, checkHistory)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (simcard_id, simcard.code, "available", None, None, datetime.now().isoformat(), None, None, None, None, "[]"))
        
        db.commit()
        
        # Return created simcard
        cursor.execute("SELECT * FROM simcards WHERE id = ?", (simcard_id,))
        created_simcard = cursor.fetchone()
        result = dict(created_simcard)
        result["checkHistory"] = json.loads(result["checkHistory"] or "[]")
        
        return result
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="SimCard code already exists")

@app.post("/simcards/bulk")
async def create_bulk_simcards(request: BulkSimCardCreate, db = Depends(get_db)):
    """Create multiple simcards at once"""
    cursor = db.cursor()
    created_cards = []
    failed_cards = []
    
    for code in request.codes:
        try:
            simcard_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO simcards 
                (id, code, status, assignedTo, assignedShopName, addedDate, saleDate, lastChecked, lastExternalCheck, externalStatus, checkHistory)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (simcard_id, code, "available", None, None, datetime.now().isoformat(), None, None, None, None, "[]"))
            created_cards.append({"id": simcard_id, "code": code})
        except sqlite3.IntegrityError:
            failed_cards.append({"code": code, "reason": "Code already exists"})
    
    db.commit()
    
    return {
        "success": True,
        "created": len(created_cards),
        "failed": len(failed_cards),
        "created_cards": created_cards,
        "failed_cards": failed_cards
    }

@app.put("/simcards/{simcard_id}")
async def update_simcard(simcard_id: str, simcard: SimCardUpdate, db = Depends(get_db)):
    cursor = db.cursor()
    
    # Check if simcard exists
    cursor.execute("SELECT * FROM simcards WHERE id = ?", (simcard_id,))
    existing_simcard = cursor.fetchone()
    if not existing_simcard:
        raise HTTPException(status_code=404, detail="SimCard not found")
    
    # Build update query dynamically
    update_fields = {}
    if simcard.code is not None:
        update_fields["code"] = simcard.code
    if simcard.status is not None:
        update_fields["status"] = simcard.status
        if simcard.status == "sold" and not existing_simcard["saleDate"]:
            update_fields["saleDate"] = datetime.now().isoformat()
    if simcard.assignedTo is not None:
        update_fields["assignedTo"] = simcard.assignedTo
    if simcard.assignedShopName is not None:
        update_fields["assignedShopName"] = simcard.assignedShopName
    
    if update_fields:
        set_clause = ", ".join([f"{key} = ?" for key in update_fields.keys()])
        values = list(update_fields.values()) + [simcard_id]
        cursor.execute(f"UPDATE simcards SET {set_clause} WHERE id = ?", values)
        db.commit()
    
    # Return updated simcard
    cursor.execute("SELECT * FROM simcards WHERE id = ?", (simcard_id,))
    updated_simcard = cursor.fetchone()
    result = dict(updated_simcard)
    result["checkHistory"] = json.loads(result["checkHistory"] or "[]")
    
    return result

@app.delete("/simcards/{simcard_id}")
async def delete_simcard(simcard_id: str, db = Depends(get_db)):
    cursor = db.cursor()
    
    # Check if simcard exists
    cursor.execute("SELECT * FROM simcards WHERE id = ?", (simcard_id,))
    simcard = cursor.fetchone()
    if not simcard:
        raise HTTPException(status_code=404, detail="SimCard not found")
    
    # Delete simcard
    cursor.execute("DELETE FROM simcards WHERE id = ?", (simcard_id,))
    db.commit()
    
    return {"success": True}

@app.post("/simcards/assign")
async def assign_simcards_to_shop(request: AssignSimCardsRequest, db = Depends(get_db)):
    cursor = db.cursor()
    
    # Check if shop exists
    cursor.execute("SELECT * FROM shops WHERE id = ?", (request.shopId,))
    shop = cursor.fetchone()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Get available simcards
    cursor.execute("SELECT * FROM simcards WHERE status = 'available' LIMIT ?", (request.count,))
    available_simcards = cursor.fetchall()
    
    if len(available_simcards) < request.count:
        raise HTTPException(status_code=400, detail=f"Only {len(available_simcards)} simcards available")
    
    # Assign simcards
    assigned_cards = []
    for simcard in available_simcards:
        cursor.execute("""
            UPDATE simcards 
            SET status = 'assigned', assignedTo = ?, assignedShopName = ?
            WHERE id = ?
        """, (request.shopId, shop["name"], simcard["id"]))
        
        assigned_cards.append({
            "id": simcard["id"],
            "code": simcard["code"],
            "status": "assigned",
            "assignedTo": request.shopId,
            "assignedShopName": shop["name"]
        })
    
    db.commit()
    
    return {
        "success": True,
        "assignedCards": assigned_cards
    }

@app.get("/simcards/{simcard_id}/check-status")
async def check_simcard_status(simcard_id: str, background_tasks: BackgroundTasks, db = Depends(get_db)):
    """Check single simcard status from external API"""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM simcards WHERE id = ?", (simcard_id,))
    simcard = cursor.fetchone()
    
    if not simcard:
        raise HTTPException(status_code=404, detail="SimCard not found")
    
    # Check external API
    external_data = await check_external_simcard_status(simcard["code"])
    
    # Update database with external data
    await update_simcard_from_external_data(db, simcard_id, simcard["code"], external_data)
    
    # Get updated simcard
    cursor.execute("SELECT * FROM simcards WHERE id = ?", (simcard_id,))
    updated_simcard = cursor.fetchone()
    result = dict(updated_simcard)
    result["checkHistory"] = json.loads(result["checkHistory"] or "[]")
    result["externalData"] = external_data
    
    return result

@app.post("/simcards/auto-check")
async def auto_check_simcards(request: Dict[str, Any], background_tasks: BackgroundTasks, db = Depends(get_db)):
    """Auto check all simcards from external API"""
    simcards = request.get("simCards", [])
    cursor = db.cursor()
    
    results = []
    timestamp = datetime.now().isoformat()
    newly_sold = []
    
    logger.info(f"Starting auto-check for {len(simcards)} simcards")
    
    for simcard_data in simcards:
        simcard_id = simcard_data.get("id")
        
        # Get current simcard from database
        cursor.execute("SELECT * FROM simcards WHERE id = ?", (simcard_id,))
        simcard = cursor.fetchone()
        
        if simcard:
            old_status = simcard["status"]
            
            # Check external API
            external_data = await check_external_simcard_status(simcard["code"])
            
            # Update database with external data
            await update_simcard_from_external_data(db, simcard_id, simcard["code"], external_data)
            
            # Get updated status
            cursor.execute("SELECT * FROM simcards WHERE id = ?", (simcard_id,))
            updated_simcard = cursor.fetchone()
            new_status = updated_simcard["status"]
            
            # Track newly sold simcards
            if old_status != "sold" and new_status == "sold":
                newly_sold.append({
                    "id": simcard_id,
                    "code": simcard["code"],
                    "shopName": simcard["assignedShopName"]
                })
            
            results.append({
                "simCardId": simcard_id,
                "status": new_status,
                "isSold": new_status == "sold",
                "saleDate": updated_simcard["saleDate"],
                "lastChecked": timestamp,
                "externalStatus": external_data.get("status"),
                "statusChanged": old_status != new_status
            })
    
    logger.info(f"Auto-check completed. Found {len(newly_sold)} newly sold simcards")
    
    return {
        "results": results,
        "timestamp": timestamp,
        "newlySold": newly_sold,
        "totalChecked": len(simcards)
    }

# Statistics endpoints
@app.get("/statistics")
async def get_statistics(db = Depends(get_db)):
    cursor = db.cursor()
    
    # Shop statistics
    cursor.execute("SELECT COUNT(*) as total FROM shops")
    total_shops = cursor.fetchone()["total"]
    
    cursor.execute("SELECT COUNT(*) as active FROM shops WHERE status = 'active'")
    active_shops = cursor.fetchone()["active"]
    
    # SimCard statistics
    cursor.execute("SELECT COUNT(*) as total FROM simcards")
    total_simcards = cursor.fetchone()["total"]
    
    cursor.execute("SELECT COUNT(*) as available FROM simcards WHERE status = 'available'")
    available_simcards = cursor.fetchone()["available"]
    
    cursor.execute("SELECT COUNT(*) as assigned FROM simcards WHERE status = 'assigned'")
    assigned_simcards = cursor.fetchone()["assigned"]
    
    cursor.execute("SELECT COUNT(*) as sold FROM simcards WHERE status = 'sold'")
    sold_simcards = cursor.fetchone()["sold"]
    
    # Region statistics
    cursor.execute("SELECT region, COUNT(*) as count FROM shops GROUP BY region")
    region_stats_result = cursor.fetchall()
    region_stats = {row["region"]: row["count"] for row in region_stats_result}
    
    # Sales by date (last 7 days based on actual sold simcards)
    cursor.execute("""
        SELECT DATE(saleDate) as sale_date, COUNT(*) as count 
        FROM simcards 
        WHERE saleDate IS NOT NULL AND DATE(saleDate) >= DATE('now', '-7 days')
        GROUP BY DATE(saleDate)
        ORDER BY sale_date DESC
    """)
    sales_data = cursor.fetchall()
    
    sales_by_date = {}
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        sales_by_date[date] = 0
    
    for sale in sales_data:
        if sale["sale_date"] in sales_by_date:
            sales_by_date[sale["sale_date"]] = sale["count"]
    
    return {
        "totalShops": total_shops,
        "activeShops": active_shops,
        "totalSimCards": total_simcards,
        "availableSimCards": available_simcards,
        "assignedSimCards": assigned_simcards,
        "soldSimCards": sold_simcards,
        "regionStats": region_stats,
        "salesByDate": sales_by_date
    }

@app.get("/statistics/shops")
async def get_shop_sales_stats(db = Depends(get_db)):
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT 
            s.id,
            s.name,
            COUNT(CASE WHEN sc.status = 'sold' THEN 1 END) as sold,
            COUNT(CASE WHEN sc.status = 'assigned' THEN 1 END) as available,
            COUNT(sc.id) as total
        FROM shops s
        LEFT JOIN simcards sc ON s.id = sc.assignedTo
        GROUP BY s.id, s.name
    """)
    
    results = cursor.fetchall()
    
    shop_stats = {}
    for result in results:
        shop_stats[result["id"]] = {
            "sold": result["sold"],
            "available": result["available"], 
            "total": result["total"]
        }
    
    return shop_stats

@app.get("/logs/status-changes")
async def get_status_change_logs(limit: int = 100, db = Depends(get_db)):
    """Get recent status change logs"""
    cursor = db.cursor()
    cursor.execute("""
        SELECT * FROM status_check_logs 
        ORDER BY timestamp DESC 
        LIMIT ?
    """, (limit,))
    
    logs = cursor.fetchall()
    result = []
    for log in logs:
        log_dict = dict(log)
        try:
            log_dict["details"] = json.loads(log_dict["details"] or "{}")
        except:
            log_dict["details"] = {}
        result.append(log_dict)
    
    return result

# Background task to periodically check all simcards
async def periodic_check_simcards():
    """Background task to periodically check all assigned simcards"""
    while True:
        try:
            logger.info("Starting periodic simcard check...")
            
            conn = sqlite3.connect(DATABASE_NAME)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all assigned simcards
            cursor.execute("SELECT * FROM simcards WHERE status = 'assigned'")
            simcards = cursor.fetchall()
            
            for simcard in simcards:
                try:
                    external_data = await check_external_simcard_status(simcard["code"])
                    await update_simcard_from_external_data(conn, simcard["id"], simcard["code"], external_data)
                    await asyncio.sleep(1)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error checking simcard {simcard['code']}: {e}")
            
            conn.close()
            logger.info(f"Periodic check completed for {len(simcards)} simcards")
            
        except Exception as e:
            logger.error(f"Error in periodic check: {e}")
        
        # Wait 30 minutes before next check
        await asyncio.sleep(30 * 60)

# Health check
@app.get("/")
async def root():
    return {
        "message": "SimCard Management API is running", 
        "version": "2.0.0",
        "features": [
            "Complete CRUD operations",
            "External API integration", 
            "Auto status checking",
            "Database logging",
            "Background monitoring"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM simcards")
        simcard_count = cursor.fetchone()[0]
        conn.close()
        
        # Test external API connection
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{EXTERNAL_API_BASE_URL}/")
                external_api_status = "ok" if response.status_code == 200 else "error"
        except:
            external_api_status = "unreachable"
        
        return {
            "status": "healthy",
            "database": "connected",
            "simcard_count": simcard_count,
            "external_api": external_api_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Start background task
@app.on_event("startup")
async def startup_event():
    """Run startup tasks"""
    logger.info("Starting SimCard Management API...")
    init_database()
    
    # Start background periodic check (optional - can be enabled/disabled)
    # asyncio.create_task(periodic_check_simcards())

if __name__ == "__main__":
    logger.info("Initializing database and starting server on port 9022...")
    init_database()
    uvicorn.run(app, host="0.0.0.0", port=9022)