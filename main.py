import os
from datetime import datetime, date
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Car, Booking, Review


app = FastAPI(title="Car Rental API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utilities
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id")) if doc.get("_id") else None
    # Convert datetime to isoformat
    for k, v in list(doc.items()):
        if isinstance(v, (datetime,)):
            doc[k] = v.isoformat()
    return doc


# Health + DB test
@app.get("/")
def read_root():
    return {"message": "Car Rental Backend Running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available" if db is None else "✅ Connected & Working",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": db.name if db is not None else None,
        "collections": []
    }
    if db is not None:
        try:
            response["collections"] = db.list_collection_names()
        except Exception as e:
            response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
    return response


# Seed some demo cars if empty (runs on first cars fetch)
SAMPLE_CARS = [
    {
        "title": "Apex GT-R",
        "brand": "Nissan",
        "model": "GT-R Nismo",
        "year": 2022,
        "type": "coupe",
        "transmission": "automatic",
        "fuel_type": "petrol",
        "seats": 4,
        "luggage": 2,
        "price_per_day": 320.0,
        "images": [
            "https://images.unsplash.com/photo-1619767886558-efdc259cde1b?q=80&w=1600&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1606664515524-ed2f786f83f2?q=80&w=1600&auto=format&fit=crop"
        ],
        "rating": 4.8,
        "featured": True
    },
    {
        "title": "Volt S",
        "brand": "Tesla",
        "model": "Model S Plaid",
        "year": 2023,
        "type": "sedan",
        "transmission": "automatic",
        "fuel_type": "electric",
        "seats": 5,
        "luggage": 3,
        "price_per_day": 280.0,
        "images": [
            "https://images.unsplash.com/photo-1549923746-c502d488b3ea?q=80&w=1600&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1549923686-1ea9789c2f73?q=80&w=1600&auto=format&fit=crop"
        ],
        "rating": 4.7,
        "featured": True
    },
    {
        "title": "Trailhawk X",
        "brand": "Jeep",
        "model": "Grand Cherokee",
        "year": 2021,
        "type": "suv",
        "transmission": "automatic",
        "fuel_type": "hybrid",
        "seats": 7,
        "luggage": 5,
        "price_per_day": 190.0,
        "images": [
            "https://images.unsplash.com/photo-1549921296-3cc26d0e3d36?q=80&w=1600&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1519648023493-d82b5f8d7fd2?q=80&w=1600&auto=format&fit=crop"
        ],
        "rating": 4.4,
        "featured": False
    }
]


def ensure_seed():
    if db is None:
        return
    if db["car"].count_documents({}) == 0:
        db["car"].insert_many(SAMPLE_CARS)


# Cars endpoints
@app.get("/api/cars")
def list_cars(
    q: Optional[str] = None,
    type: Optional[str] = None,
    brand: Optional[str] = None,
    transmission: Optional[str] = None,
    fuel_type: Optional[str] = None,
    seats: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort: Optional[str] = Query("popular", description="popular|price_asc|price_desc|newest"),
    limit: int = 50,
):
    ensure_seed()
    if db is None:
        return []

    filt: Dict[str, Any] = {}
    if q:
        filt["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"brand": {"$regex": q, "$options": "i"}},
            {"model": {"$regex": q, "$options": "i"}},
        ]
    if type:
        filt["type"] = type
    if brand:
        filt["brand"] = brand
    if transmission:
        filt["transmission"] = transmission
    if fuel_type:
        filt["fuel_type"] = fuel_type
    if seats:
        filt["seats"] = seats
    if min_price is not None or max_price is not None:
        price_cond: Dict[str, Any] = {}
        if min_price is not None:
            price_cond["$gte"] = min_price
        if max_price is not None:
            price_cond["$lte"] = max_price
        filt["price_per_day"] = price_cond

    sort_spec = None
    if sort == "price_asc":
        sort_spec = ("price_per_day", 1)
    elif sort == "price_desc":
        sort_spec = ("price_per_day", -1)
    elif sort == "newest":
        sort_spec = ("year", -1)
    else:
        sort_spec = ("rating", -1)

    cursor = db["car"].find(filt).limit(limit).sort([sort_spec])
    return [serialize_doc(d) for d in cursor]


@app.get("/api/cars/{car_id}")
def get_car(car_id: str):
    ensure_seed()
    if db is None:
        raise HTTPException(status_code=404, detail="Database not available")
    try:
        doc = db["car"].find_one({"_id": ObjectId(car_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid car id")
    if not doc:
        raise HTTPException(status_code=404, detail="Car not found")
    return serialize_doc(doc)


# Booking endpoints
class BookingIn(Booking):
    pass


@app.post("/api/bookings")
def create_booking(payload: BookingIn):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    # Basic availability check (no overlapping bookings)
    try:
        car_oid = ObjectId(payload.car_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid car id")

    overlap = db["booking"].count_documents({
        "car_id": payload.car_id,
        "status": {"$in": ["active", "confirmed"]},
        "$or": [
            {"pickup_date": {"$lte": payload.dropoff_date.isoformat()}, "dropoff_date": {"$gte": payload.pickup_date.isoformat()}},
        ]
    })
    if overlap > 0:
        raise HTTPException(status_code=409, detail="Selected dates are not available")

    # Simple cost calc
    days = (payload.dropoff_date - payload.pickup_date).days
    if days <= 0:
        raise HTTPException(status_code=400, detail="Drop-off must be after pickup")
    car = db["car"].find_one({"_id": car_oid})
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    total_cost = round(days * float(car.get("price_per_day", 0)), 2)

    booking_data = payload.model_dump()
    booking_data["pickup_date"] = payload.pickup_date.isoformat()
    booking_data["dropoff_date"] = payload.dropoff_date.isoformat()
    booking_data["total_cost"] = total_cost

    booking_id = create_document("booking", booking_data)
    return {"id": booking_id, "total_cost": total_cost, "status": "confirmed"}


@app.get("/api/bookings")
def list_bookings(email: Optional[EmailStr] = None):
    if db is None:
        return []
    filt: Dict[str, Any] = {}
    if email:
        filt["email"] = str(email)
    cursor = db["booking"].find(filt).sort([("created_at", -1)])
    return [serialize_doc(d) for d in cursor]


# Reviews
class ReviewIn(Review):
    pass


@app.post("/api/reviews")
def add_review(payload: ReviewIn):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    # Validate car
    try:
        _ = ObjectId(payload.car_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid car id")

    review_id = create_document("review", payload)
    return {"id": review_id}


@app.get("/api/reviews")
def list_reviews(car_id: Optional[str] = None, limit: int = 20):
    if db is None:
        return []
    filt: Dict[str, Any] = {}
    if car_id:
        filt["car_id"] = car_id
    cursor = db["review"].find(filt).limit(limit).sort([("created_at", -1)])
    return [serialize_doc(d) for d in cursor]


# FAQs and Contact
@app.get("/api/faqs")
def get_faqs():
    return [
        {"q": "What documents do I need to rent a car?", "a": "A valid driver license and a credit card."},
        {"q": "How is the rental price calculated?", "a": "Per-day rate multiplied by number of rental days plus optional extras."},
        {"q": "What is the fuel policy?", "a": "Full-to-full unless stated otherwise."},
        {"q": "Can I cancel my booking?", "a": "Yes. Free cancellation up to 24 hours before pickup for most cars."},
    ]


class ContactMessage(BaseModel):
    name: str
    email: EmailStr
    message: str


@app.post("/api/contact")
def submit_contact(msg: ContactMessage):
    _id = create_document("contact", msg)
    return {"id": _id, "ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
