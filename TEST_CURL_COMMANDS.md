# 🧪 Fast Drop API — Test Commands (Curl & Swagger JSON)
# أوامر اختبار كل الـ Endpoints (للكونسول وللـ Swagger)

> **Base URL:** `http://localhost:8000`
> **Swagger UI:** `http://localhost:8000/docs`
> **ReDoc:** `http://localhost:8000/redoc`
> **الإجمالي:** 14 AI Endpoint + 22 Core Endpoint

---

## ❤️ 1. Health & Root — حالة السيرفر

### Root — الصفحة الرئيسية (`GET /`)
**Curl:**
```bash
curl -s http://localhost:8000/
```
*(No JSON body required)*

### Health Check — فحص صحة السيرفر (`GET /health`)
**Curl:**
```bash
curl -s http://localhost:8000/health
```
*(No JSON body required — يرجع حالة DB, Redis, RAG)*

### List Zones — كل مناطق التوصيل (`GET /api/zones`)
**Curl:**
```bash
curl -s http://localhost:8000/api/zones
```
*(No JSON body required)*

---

## 🔑 2. Authentication — التسجيل وتسجيل الدخول

> **ملاحظة:** جميع Auth endpoints تحت prefix `/api/auth/`

### Register — تسجيل مستخدم جديد (`POST /api/auth/register`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"ahmed_test\", \"email\": \"ahmed@test.com\", \"password\": \"Pass1234\", \"role\": \"customer\"}"
```
**Swagger JSON:**
```json
{
  "username": "ahmed_test",
  "email": "ahmed@test.com",
  "password": "Pass1234",
  "role": "customer"
}
```
> Roles: `customer` | `driver` | `admin`

### Login — تسجيل الدخول (`POST /api/auth/login`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"ahmed_test\", \"password\": \"Pass1234\"}"
```
**Swagger JSON:**
```json
{
  "username": "ahmed_test",
  "password": "Pass1234"
}
```
> ترجع `access_token` و `refresh_token` و `role`

### Refresh Token — تجديد التوكن (`POST /api/auth/refresh`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/auth/refresh \
  -H "Authorization: Bearer YOUR_REFRESH_TOKEN_HERE"
```
> استخدم الـ `refresh_token` من الـ Login response

### Get Me — بيانات المستخدم الحالي (`GET /api/auth/me`)
**Curl:**
```bash
curl -s http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"
```

---

## 📦 3. Orders — الأوردرات

### Create Order — إنشاء أوردر جديد (`POST /api/orders/`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/orders/ \
  -H "Content-Type: application/json" \
  -d "{\"customer_id\": 1, \"pickup_address\": \"12 شارع طلعت حرب، وسط البلد، القاهرة\", \"delivery_address\": \"45 شارع مكرم عبيد، مدينة نصر، القاهرة\", \"weight_kg\": 3.5, \"cod_amount\": 250.0, \"notes_ar\": \"اتصل قبل التوصيل\"}"
```
**Swagger JSON:**
```json
{
  "customer_id": 1,
  "pickup_address": "12 شارع طلعت حرب، وسط البلد، القاهرة",
  "delivery_address": "45 شارع مكرم عبيد، مدينة نصر، القاهرة",
  "weight_kg": 3.5,
  "cod_amount": 250.0,
  "notes_ar": "اتصل قبل التوصيل"
}
```

### List Orders — عرض كل الأوردرات (`GET /api/orders/`)
**Curl:**
```bash
curl -s "http://localhost:8000/api/orders/?limit=20"
```
*(Query params اختيارية: `status`, `limit`)*

**مع فلتر الحالة:**
```bash
curl -s "http://localhost:8000/api/orders/?status=Pending&limit=10"
```
> حالات الأوردر: `Pending` | `Assigned` | `PickedUp` | `OutForDelivery` | `Delivered` | `Failed` | `Cancelled`

### Order Stats — إحصائيات الأوردرات (`GET /api/orders/stats`)
**Curl:**
```bash
curl -s http://localhost:8000/api/orders/stats
```
*(يرجع عدد الأوردرات لكل حالة)*

### Get Order by ID — عرض أوردر بالرقم (`GET /api/orders/{order_id}`)
**Curl:**
```bash
curl -s http://localhost:8000/api/orders/ORD-2026-00001
```

### Update Order Status — تحديث حالة الأوردر (`PATCH /api/orders/{order_id}/status`)
> ⚠️ **تصحيح:** الـ method هو `PATCH` مش `PUT`، والـ body هو JSON مش query param

**Curl:**
```bash
curl -s -X PATCH http://localhost:8000/api/orders/ORD-2026-00001/status \
  -H "Content-Type: application/json" \
  -d "{\"status\": \"Assigned\"}"
```
**Swagger JSON:**
```json
{
  "status": "Assigned"
}
```

### Customer Orders — أوردرات عميل معين (`GET /api/orders/customer/{customer_id}`)
**Curl:**
```bash
curl -s "http://localhost:8000/api/orders/customer/1?limit=20"
```

---

## 🚗 4. Drivers — السواقين

### Create Driver — تسجيل سواق جديد (`POST /api/drivers/`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/drivers/ \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"حسن محمد\", \"phone\": \"+201012345678\", \"vehicle_type\": \"motorcycle\", \"max_weight_kg\": 20.0}"
```
**Swagger JSON:**
```json
{
  "name": "حسن محمد",
  "phone": "+201012345678",
  "vehicle_type": "motorcycle",
  "max_weight_kg": 20.0
}
```
> Vehicle types: `motorcycle` | `car` | `van` | `truck`

### List Drivers — عرض كل السواقين (`GET /api/drivers/`)
**Curl:**
```bash
curl -s "http://localhost:8000/api/drivers/?limit=50"
```
*(Query params اختيارية: `status`, `zone_id`, `limit`)*

### Available Drivers — السواقين المتاحين فقط (`GET /api/drivers/available`)
**Curl:**
```bash
curl -s http://localhost:8000/api/drivers/available
```

### Get Driver by ID — بيانات سواق (`GET /api/drivers/{driver_id}`)
**Curl:**
```bash
curl -s http://localhost:8000/api/drivers/1
```

### Update Driver Status — تحديث حالة السواق (`PATCH /api/drivers/{driver_id}/status`)
**Curl:**
```bash
curl -s -X PATCH "http://localhost:8000/api/drivers/1/status?status=available"
```
> حالات السواق: `available` | `busy` | `offline`

### Update Driver Location — تحديث موقع السواق (`POST /api/drivers/{driver_id}/location`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/drivers/1/location \
  -H "Content-Type: application/json" \
  -d "{\"lat\": 30.051, \"lng\": 31.365, \"accuracy_meters\": 15.0}"
```
**Swagger JSON:**
```json
{
  "lat": 30.051,
  "lng": 31.365,
  "accuracy_meters": 15.0
}
```

### Find Nearest Drivers — أقرب سواقين للموقع (`POST /api/drivers/nearest`)
> ⚠️ **تصحيح:** الحقل الصح هو `max_distance_km` مش `radius_km`

**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/drivers/nearest \
  -H "Content-Type: application/json" \
  -d "{\"lat\": 30.044, \"lng\": 31.235, \"max_distance_km\": 5}"
```
**Swagger JSON:**
```json
{
  "lat": 30.044,
  "lng": 31.235,
  "max_distance_km": 5
}
```

### Driver Score — نقاط أداء السواق (`GET /api/drivers/{driver_id}/score`)
**Curl:**
```bash
curl -s http://localhost:8000/api/drivers/1/score
```

### Driver Leaderboard — ترتيب السواقين (`GET /api/drivers/leaderboard/top`)
**Curl:**
```bash
curl -s http://localhost:8000/api/drivers/leaderboard/top
```

---

## 📊 5. Analytics — التحليلات

### Natural Language Query — استعلام بالعربي أو الإنجليزي (`POST /api/analytics/query`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/analytics/query \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"كام أوردر اتعمل النهاردة؟\", \"language\": \"ar\"}"
```
**Swagger JSON:**
```json
{
  "question": "كام أوردر اتعمل النهاردة؟",
  "language": "ar"
}
```
> أسئلة تانية: `"مين أحسن سواق الأسبوع ده؟"` | `"Which zone has the most failed deliveries?"`

### Dashboard — لوحة التحكم السريعة (`GET /api/analytics/dashboard`)
**Curl:**
```bash
curl -s http://localhost:8000/api/analytics/dashboard
```

### Revenue Stats — إحصائيات الإيرادات (`GET /api/analytics/revenue`)
**Curl:**
```bash
curl -s http://localhost:8000/api/analytics/revenue
```

### Rate Limit Stats — استخدام LLM API (`GET /api/analytics/rate-limits`)
**Curl:**
```bash
curl -s http://localhost:8000/api/analytics/rate-limits
```

### Cache Stats — إحصائيات RAG Cache (`GET /api/analytics/cache-stats`)
**Curl:**
```bash
curl -s http://localhost:8000/api/analytics/cache-stats
```

---

## 💬 6. Chat — الشات بوت

> ⚠️ **تصحيح:** الـ schema لا يحتوي على `session_id`، الحقل الاختياري هو `customer_id`

### Ask Chat Bot — كلم البوت (`POST /api/chat/`)
**Curl 1 (Policy query — بالعربي):**
```bash
curl -s -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"إيه مناطق التوصيل اللي عندكم في القاهرة؟\", \"customer_id\": 1}"
```
**Swagger JSON 1:**
```json
{
  "message": "إيه مناطق التوصيل اللي عندكم في القاهرة؟",
  "customer_id": 1
}
```

**Curl 2 (Arabizi):**
```bash
curl -s -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"feen el order bta3y ORD-2026-00001\"}"
```
**Swagger JSON 2:**
```json
{
  "message": "feen el order bta3y ORD-2026-00001"
}
```

**Curl 3 (English):**
```bash
curl -s -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"What are your delivery fees?\"}"
```

---

## ═══════════════════════════════════════════════
## 🤖 AI Engine Endpoints (14 Total)
## ═══════════════════════════════════════════════

## 🗺️ 7. Cluster Orders (`POST /api/ai/cluster-orders`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/ai/cluster-orders \
  -H "Content-Type: application/json" \
  -d "{\"orders\": [{\"id\": \"ORD-1\", \"lat\": 30.044, \"lng\": 31.235, \"weight_kg\": 2}, {\"id\": \"ORD-2\", \"lat\": 30.051, \"lng\": 31.365, \"weight_kg\": 3}, {\"id\": \"ORD-3\", \"lat\": 30.055, \"lng\": 31.368, \"weight_kg\": 1.5}, {\"id\": \"ORD-4\", \"lat\": 30.048, \"lng\": 31.360, \"weight_kg\": 4}, {\"id\": \"ORD-5\", \"lat\": 29.960, \"lng\": 31.256, \"weight_kg\": 2}], \"eps_km\": 3.0, \"min_samples\": 2}"
```
**Swagger JSON:**
```json
{
  "orders": [
    {"id": "ORD-1", "lat": 30.044, "lng": 31.235, "weight_kg": 2},
    {"id": "ORD-2", "lat": 30.051, "lng": 31.365, "weight_kg": 3},
    {"id": "ORD-3", "lat": 30.055, "lng": 31.368, "weight_kg": 1.5},
    {"id": "ORD-4", "lat": 30.048, "lng": 31.360, "weight_kg": 4},
    {"id": "ORD-5", "lat": 29.960, "lng": 31.256, "weight_kg": 2}
  ],
  "eps_km": 3.0,
  "min_samples": 2
}
```

---

## 🛣️ 8. Optimize Route (`POST /api/ai/optimize-route`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/ai/optimize-route \
  -H "Content-Type: application/json" \
  -d "{\"orders\": [{\"id\": \"ORD-2\", \"lat\": 30.051, \"lng\": 31.365, \"weight_kg\": 3}, {\"id\": \"ORD-3\", \"lat\": 30.055, \"lng\": 31.368, \"weight_kg\": 1.5}, {\"id\": \"ORD-4\", \"lat\": 30.048, \"lng\": 31.360, \"weight_kg\": 4}], \"depot_lat\": 30.044, \"depot_lng\": 31.235, \"num_vehicles\": 1, \"max_weight_kg\": 50.0}"
```
**Swagger JSON:**
```json
{
  "orders": [
    {"id": "ORD-2", "lat": 30.051, "lng": 31.365, "weight_kg": 3},
    {"id": "ORD-3", "lat": 30.055, "lng": 31.368, "weight_kg": 1.5},
    {"id": "ORD-4", "lat": 30.048, "lng": 31.360, "weight_kg": 4}
  ],
  "depot_lat": 30.044,
  "depot_lng": 31.235,
  "num_vehicles": 1,
  "max_weight_kg": 50.0
}
```

---

## 🚀 9. Full Dispatch (`POST /api/ai/dispatch`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/ai/dispatch \
  -H "Content-Type: application/json" \
  -d "{\"orders\": [{\"id\": \"ORD-1\", \"lat\": 30.044, \"lng\": 31.235, \"weight_kg\": 2}, {\"id\": \"ORD-2\", \"lat\": 30.051, \"lng\": 31.365, \"weight_kg\": 3}, {\"id\": \"ORD-3\", \"lat\": 30.055, \"lng\": 31.368, \"weight_kg\": 1.5}, {\"id\": \"ORD-4\", \"lat\": 30.048, \"lng\": 31.360, \"weight_kg\": 4}, {\"id\": \"ORD-5\", \"lat\": 29.960, \"lng\": 31.256, \"weight_kg\": 2}], \"drivers\": [{\"id\": 1, \"name\": \"Hassan\", \"max_weight_kg\": 20, \"performance_score\": 0.92}, {\"id\": 2, \"name\": \"Karim\", \"max_weight_kg\": 50, \"performance_score\": 0.95}]}"
```
**Swagger JSON:**
```json
{
  "orders": [
    {"id": "ORD-1", "lat": 30.044, "lng": 31.235, "weight_kg": 2},
    {"id": "ORD-2", "lat": 30.051, "lng": 31.365, "weight_kg": 3},
    {"id": "ORD-3", "lat": 30.055, "lng": 31.368, "weight_kg": 1.5},
    {"id": "ORD-4", "lat": 30.048, "lng": 31.360, "weight_kg": 4},
    {"id": "ORD-5", "lat": 29.960, "lng": 31.256, "weight_kg": 2}
  ],
  "drivers": [
    {"id": 1, "name": "Hassan", "max_weight_kg": 20, "performance_score": 0.92},
    {"id": 2, "name": "Karim", "max_weight_kg": 50, "performance_score": 0.95}
  ]
}
```

---

## ⏰ 10. Detect Delay (`POST /api/ai/detect-delay`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/ai/detect-delay \
  -H "Content-Type: application/json" \
  -d "{\"current_time\": \"2026-03-06T17:00:00\", \"estimated_arrival\": \"2026-03-06T17:20:00\", \"actual_progress_pct\": 0.3, \"expected_progress_pct\": 0.7}"
```
**Swagger JSON:**
```json
{
  "current_time": "2026-03-06T17:00:00",
  "estimated_arrival": "2026-03-06T17:20:00",
  "actual_progress_pct": 0.3,
  "expected_progress_pct": 0.7
}
```

---

## 🔄 11. Reroute (`POST /api/ai/reroute`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/ai/reroute \
  -H "Content-Type: application/json" \
  -d "{\"remaining_stops\": [{\"order_id\": \"ORD-2\", \"lat\": 30.051, \"lng\": 31.365, \"weight_kg\": 3}, {\"order_id\": \"ORD-3\", \"lat\": 30.055, \"lng\": 31.368, \"weight_kg\": 1.5}], \"current_lat\": 30.060, \"current_lng\": 31.370}"
```
**Swagger JSON:**
```json
{
  "remaining_stops": [
    {"order_id": "ORD-2", "lat": 30.051, "lng": 31.365, "weight_kg": 3},
    {"order_id": "ORD-3", "lat": 30.055, "lng": 31.368, "weight_kg": 1.5}
  ],
  "current_lat": 30.060,
  "current_lng": 31.370
}
```

---

## 📢 12. Arabic Alert (`POST /api/ai/alert`)
**Curl (Customer Alert):**
```bash
curl -s -X POST http://localhost:8000/api/ai/alert \
  -H "Content-Type: application/json" \
  -d "{\"order_id\": \"ORD-2026-51318\", \"delay_info\": {\"delayed\": true, \"severity\": \"major\", \"extra_minutes\": 11}, \"alert_type\": \"customer\"}"
```
**Swagger JSON:**
```json
{
  "order_id": "ORD-2026-51318",
  "delay_info": {
    "delayed": true,
    "severity": "major",
    "extra_minutes": 11
  },
  "alert_type": "customer"
}
```

**Curl (Driver Alert with New Route):**
```bash
curl -s -X POST http://localhost:8000/api/ai/alert \
  -H "Content-Type: application/json" \
  -d "{\"order_id\": \"ORD-2026-51318\", \"delay_info\": {\"delayed\": true, \"severity\": \"minor\", \"extra_minutes\": 5}, \"alert_type\": \"driver\", \"new_route\": [{\"order_id\": \"ORD-3\", \"lat\": 30.055, \"lng\": 31.368}]}"
```
> `alert_type`: `"customer"` أو `"driver"`

---

## ⏱️ 13. Predict ETA (`POST /api/ai/predict-eta`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/ai/predict-eta \
  -H "Content-Type: application/json" \
  -d "{\"pickup_lat\": 29.960, \"pickup_lng\": 31.256, \"delivery_lat\": 30.007, \"delivery_lng\": 31.491, \"zone_name\": \"New Cairo (5th Settlement)\", \"current_time\": \"2026-03-06T17:00:00\"}"
```
**Swagger JSON:**
```json
{
  "pickup_lat": 29.960,
  "pickup_lng": 31.256,
  "delivery_lat": 30.007,
  "delivery_lng": 31.491,
  "zone_name": "New Cairo (5th Settlement)",
  "current_time": "2026-03-06T17:00:00"
}
```
> `current_time` و `zone_name` اختياريان

---

## 📈 14. Forecast Demand (`POST /api/ai/forecast-demand`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/ai/forecast-demand \
  -H "Content-Type: application/json" \
  -d "{\"zone_name\": \"Nasr City\", \"hours_ahead\": 4}"
```
**Swagger JSON:**
```json
{
  "zone_name": "Nasr City",
  "hours_ahead": 4
}
```
> `zone_name` و `target_date` اختياريان — بدونهم يعمل forecast لكل المناطق من دلوقتي

---

## 🚨 15. Check Anomaly (`POST /api/ai/check-anomaly`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/ai/check-anomaly \
  -H "Content-Type: application/json" \
  -d "{\"customer_id\": 99, \"pickup_lat\": 30.044, \"pickup_lng\": 31.235, \"delivery_lat\": 30.044, \"delivery_lng\": 31.236, \"weight_kg\": 250, \"cod_amount\": 25000, \"recent_order_count\": 15}"
```
**Swagger JSON:**
```json
{
  "customer_id": 99,
  "pickup_lat": 30.044,
  "pickup_lng": 31.235,
  "delivery_lat": 30.044,
  "delivery_lng": 31.236,
  "weight_kg": 250,
  "cod_amount": 25000,
  "recent_order_count": 15
}
```

---

## 🎯 16. Smart Driver Matching (`POST /api/ai/match-driver`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/ai/match-driver \
  -H "Content-Type: application/json" \
  -d "{\"order\": {\"id\": \"ORD-100\", \"lat\": 30.051, \"lng\": 31.365, \"weight_kg\": 5}, \"drivers\": [{\"id\": 1, \"name\": \"Hassan\", \"lat\": 30.055, \"lng\": 31.368, \"max_weight_kg\": 20, \"performance_score\": 0.95, \"current_orders\": 2, \"vehicle_type\": \"motorcycle\"}, {\"id\": 2, \"name\": \"Karim\", \"lat\": 29.960, \"lng\": 31.256, \"max_weight_kg\": 50, \"performance_score\": 0.88, \"current_orders\": 8, \"vehicle_type\": \"motorcycle\"}, {\"id\": 3, \"name\": \"Mohamed\", \"lat\": 30.044, \"lng\": 31.235, \"max_weight_kg\": 10, \"performance_score\": 0.92, \"current_orders\": 0, \"vehicle_type\": \"motorcycle\"}]}"
```
**Swagger JSON:**
```json
{
  "order": {
    "id": "ORD-100",
    "lat": 30.051,
    "lng": 31.365,
    "weight_kg": 5
  },
  "drivers": [
    {
      "id": 1,
      "name": "Hassan",
      "lat": 30.055,
      "lng": 31.368,
      "max_weight_kg": 20,
      "performance_score": 0.95,
      "current_orders": 2,
      "vehicle_type": "motorcycle"
    },
    {
      "id": 2,
      "name": "Karim",
      "lat": 29.960,
      "lng": 31.256,
      "max_weight_kg": 50,
      "performance_score": 0.88,
      "current_orders": 8,
      "vehicle_type": "motorcycle"
    },
    {
      "id": 3,
      "name": "Mohamed",
      "lat": 30.044,
      "lng": 31.235,
      "max_weight_kg": 10,
      "performance_score": 0.92,
      "current_orders": 0,
      "vehicle_type": "motorcycle"
    }
  ]
}
```

---

## 💰 17. Dynamic Pricing (`POST /api/ai/dynamic-pricing`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/ai/dynamic-pricing \
  -H "Content-Type: application/json" \
  -d "{\"pickup_lat\": 30.044, \"pickup_lng\": 31.235, \"delivery_lat\": 30.007, \"delivery_lng\": 31.491, \"weight_kg\": 8, \"cod_amount\": 500, \"zone_name\": \"New Cairo (5th Settlement)\", \"demand_level\": \"high\", \"current_time\": \"2026-03-06T17:30:00\"}"
```
**Swagger JSON:**
```json
{
  "pickup_lat": 30.044,
  "pickup_lng": 31.235,
  "delivery_lat": 30.007,
  "delivery_lng": 31.491,
  "weight_kg": 8,
  "cod_amount": 500,
  "zone_name": "New Cairo (5th Settlement)",
  "demand_level": "high",
  "current_time": "2026-03-06T17:30:00"
}
```
> `demand_level`: `low` | `normal` | `high` | `surge`

---

## 😊😠 18. Sentiment Analysis (`POST /api/ai/analyze-sentiment`)
**Curl (Negative — English):**
```bash
curl -s -X POST http://localhost:8000/api/ai/analyze-sentiment \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"terrible service, worst delivery ever, I am angry and want a refund immediately urgent\"}"
```
**Curl (Negative — Arabic):**
```bash
curl -s -X POST http://localhost:8000/api/ai/analyze-sentiment \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"خدمة سيئة جداً وأنا زعلان جداً من التأخير\"}"
```
**Swagger JSON:**
```json
{
  "message": "terrible service, worst delivery ever, I am angry and want a refund immediately urgent"
}
```

---

## 📊 19. Driver Behavior (`POST /api/ai/driver-behavior`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/ai/driver-behavior \
  -H "Content-Type: application/json" \
  -d "{\"driver_id\": 1, \"deliveries_completed\": 450, \"deliveries_failed\": 12, \"avg_delivery_time_min\": 18, \"cancellation_count\": 5, \"customer_complaints\": 0, \"avg_rating\": 4.9, \"days_active\": 60, \"total_distance_km\": 3200}"
```
**Swagger JSON:**
```json
{
  "driver_id": 1,
  "deliveries_completed": 450,
  "deliveries_failed": 12,
  "avg_delivery_time_min": 18,
  "cancellation_count": 5,
  "customer_complaints": 0,
  "avg_rating": 4.9,
  "days_active": 60,
  "total_distance_km": 3200
}
```

---

## 🗺️ 20. Zone Heatmap (`POST /api/ai/zone-heatmap`)
**Curl:**
```bash
curl -s -X POST http://localhost:8000/api/ai/zone-heatmap \
  -H "Content-Type: application/json" \
  -d "{\"current_time\": \"2026-03-06T17:00:00\", \"include_forecast\": true}"
```
**Swagger JSON:**
```json
{
  "current_time": "2026-03-06T17:00:00",
  "include_forecast": true
}
```
> بدون body تماماً يشتغل بالوقت الحالي: `curl -s -X POST http://localhost:8000/api/ai/zone-heatmap -H "Content-Type: application/json" -d "{}"`

---

## 🔄 Quick Test All (One-liner for Windows CMD)
Run all critical endpoints in sequence:
```bash
curl -s http://localhost:8000/health && echo " ✅ Health" && curl -s -X POST http://localhost:8000/api/ai/predict-eta -H "Content-Type: application/json" -d "{\"pickup_lat\":30.044,\"pickup_lng\":31.235,\"delivery_lat\":30.051,\"delivery_lng\":31.365}" > nul && echo " ✅ ETA" && curl -s -X POST http://localhost:8000/api/ai/forecast-demand -H "Content-Type: application/json" -d "{\"zone_name\":\"Downtown\",\"hours_ahead\":3}" > nul && echo " ✅ Demand" && curl -s -X POST http://localhost:8000/api/ai/check-anomaly -H "Content-Type: application/json" -d "{\"customer_id\":1,\"pickup_lat\":30.044,\"pickup_lng\":31.235,\"delivery_lat\":30.051,\"delivery_lng\":31.365,\"weight_kg\":3}" > nul && echo " ✅ Anomaly" && curl -s -X POST http://localhost:8000/api/ai/dynamic-pricing -H "Content-Type: application/json" -d "{\"pickup_lat\":30.044,\"pickup_lng\":31.235,\"delivery_lat\":30.051,\"delivery_lng\":31.365}" > nul && echo " ✅ Pricing" && curl -s -X POST http://localhost:8000/api/ai/analyze-sentiment -H "Content-Type: application/json" -d "{\"message\":\"great service\"}" > nul && echo " ✅ Sentiment" && curl -s -X POST http://localhost:8000/api/ai/zone-heatmap -H "Content-Type: application/json" -d "{}" > nul && echo " ✅ Heatmap"
```

---

## 📋 ملخص جميع الـ Endpoints

| # | Method | Path | وصف |
|---|--------|------|-----|
| 1 | GET | `/` | Root / Info |
| 2 | GET | `/health` | Health Check |
| 3 | GET | `/api/zones` | List Zones |
| 4 | POST | `/api/auth/register` | Register User |
| 5 | POST | `/api/auth/login` | Login |
| 6 | POST | `/api/auth/refresh` | Refresh Token |
| 7 | GET | `/api/auth/me` | Current User |
| 8 | POST | `/api/orders/` | Create Order |
| 9 | GET | `/api/orders/` | List Orders |
| 10 | GET | `/api/orders/stats` | Order Stats |
| 11 | GET | `/api/orders/{id}` | Get Order |
| 12 | PATCH | `/api/orders/{id}/status` | Update Status |
| 13 | GET | `/api/orders/customer/{id}` | Customer Orders |
| 14 | POST | `/api/drivers/` | Create Driver |
| 15 | GET | `/api/drivers/` | List Drivers |
| 16 | GET | `/api/drivers/available` | Available Drivers |
| 17 | GET | `/api/drivers/{id}` | Get Driver |
| 18 | PATCH | `/api/drivers/{id}/status` | Update Driver Status |
| 19 | POST | `/api/drivers/{id}/location` | GPS Update |
| 20 | POST | `/api/drivers/nearest` | Nearest Drivers |
| 21 | GET | `/api/drivers/{id}/score` | Driver Score |
| 22 | GET | `/api/drivers/leaderboard/top` | Leaderboard |
| 23 | POST | `/api/analytics/query` | NLP Analytics |
| 24 | GET | `/api/analytics/dashboard` | Dashboard |
| 25 | GET | `/api/analytics/revenue` | Revenue Stats |
| 26 | GET | `/api/analytics/rate-limits` | Rate Limits |
| 27 | GET | `/api/analytics/cache-stats` | Cache Stats |
| 28 | POST | `/api/chat/` | Chatbot |
| 29 | POST | `/api/ai/cluster-orders` | DBSCAN Clustering |
| 30 | POST | `/api/ai/optimize-route` | VRP Route Opt |
| 31 | POST | `/api/ai/dispatch` | Full Dispatch |
| 32 | POST | `/api/ai/detect-delay` | Delay Detection |
| 33 | POST | `/api/ai/reroute` | Reroute |
| 34 | POST | `/api/ai/alert` | Arabic Alert |
| 35 | POST | `/api/ai/predict-eta` | ETA Prediction |
| 36 | POST | `/api/ai/forecast-demand` | Demand Forecast |
| 37 | POST | `/api/ai/check-anomaly` | Anomaly Detection |
| 38 | POST | `/api/ai/match-driver` | Driver Matching |
| 39 | POST | `/api/ai/dynamic-pricing` | Dynamic Pricing |
| 40 | POST | `/api/ai/analyze-sentiment` | Sentiment Analysis |
| 41 | POST | `/api/ai/driver-behavior` | Driver Behavior |
| 42 | POST | `/api/ai/zone-heatmap` | Zone Heatmap |
