# SimCard Management Server

## To'liq ishlaydigan Python API server

### Tez ishga tushirish:

**BARCHA SERVERLARNI BIRGA ISHGA TUSHIRISH:**
```bash
python start_servers.py
```

### Manual ishga tushirish:

1. **Python kutubxonalarini o'rnatish:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Asosiy API serverni ishga tushirish (9022 port):**
   ```bash
   python malin.py
   ```

3. **SimCard status API serverni ishga tushirish (9020 port):**
   ```bash
   python simcard_status_api.py
   ```

4. **Web ilovani ishga tushirish:**
   ```bash
   npm run dev
   ```

### Xususiyatlari:

#### Asosiy API Server (malin.py - Port 9022):
- ✅ To'liq CRUD operatsiyalar (shops va simcards)
- ✅ Tashqi API bilan integratsiya
- ✅ Avtomatik holat tekshirish
- ✅ Bazaga ma'lumot saqlash
- ✅ Status o'zgarishlarini kuzatish
- ✅ Fon rejimida monitoring
- ✅ Bulk simkarta qo'shish
- ✅ Shop statistikalari
- ✅ Health check endpointlari

#### SimCard Status API (simcard_status_api.py - Port 9020):
- ✅ Simkarta holatini tekshirish
- ✅ Bulk holat tekshirish
- ✅ Bazadan ma'lumot olish

### API Endpointlari:

#### Autentifikatsiya:
- `POST /auth/login` - Kirish
- `POST /auth/logout` - Chiqish

#### Magazinlar:
- `GET /shops` - Barcha magazinlar
- `POST /shops` - Yangi magazin
- `PUT /shops/{shop_id}` - Magazin yangilash
- `DELETE /shops/{shop_id}` - Magazin o'chirish
- `GET /shops/{shop_id}/stats` - Magazin statistikasi

#### Simkartalar:
- `GET /simcards` - Barcha simkartalar
- `POST /simcards` - Yangi simkarta
- `POST /simcards/bulk` - Bulk simkarta qo'shish
- `PUT /simcards/{simcard_id}` - Simkarta yangilash
- `DELETE /simcards/{simcard_id}` - Simkarta o'chirish
- `POST /simcards/assign` - Simkartalarni magazinga tayinlash
- `GET /simcards/{simcard_id}/check-status` - Bitta simkarta holatini tekshirish
- `POST /simcards/auto-check` - Avtomatik barcha simkartalarni tekshirish

#### Statistika:
- `GET /statistics` - Umumiy statistika
- `GET /statistics/shops` - Magazinlar statistikasi
- `GET /logs/status-changes` - Status o'zgarish loglari

#### Monitoring:
- `GET /` - API ma'lumotlari
- `GET /health` - Tizim holati

### Tashqi API integratsiyasi:

Server avtomatik ravishda tashqi manbalardan simkarta holatini tekshiradi va natijalarni bazaga saqlaydi:

1. **Auto-check jarayoni**: 
   - Barcha tayinlangan simkartalarni tekshiradi
   - Tashqi API dan ma'lumot oladi
   - Status o'zgarishlarini bazaga saqlaydi
   - Yangi sotilgan simkartalar haqida xabar beradi

2. **Manual check**:
   - Bitta simkarta holatini darhol tekshirish
   - Real-time ma'lumot olish

3. **Logging sistema**:
   - Barcha status o'zgarishlari saqlanadi
   - Tekshirish tarixi
   - Xato holatlarni kuzatish

### Ma'lumotlar bazasi:

SQLite bazasi quyidagi jadvallardan iborat:
- `shops` - Magazin ma'lumotlari
- `simcards` - Simkarta ma'lumotlari (kengaytirilgan)
- `users` - Foydalanuvchilar
- `status_check_logs` - Status o'zgarish loglari

### Konfiguratsiya:

- **Main API Port**: 9022
- **Status API Port**: 9020  
- **Database**: simcard_db.sqlite
- **External API Timeout**: 10 soniya
- **Auto-check Interval**: 30 daqiqa (o'chirilgan, kerak bo'lganda yoqiladi)

Server to'liq ishlaydigan va web ilovaga barcha kerakli ma'lumotlarni taqdim etadi!