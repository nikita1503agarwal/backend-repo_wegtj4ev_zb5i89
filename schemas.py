"""
Database Schemas for Car Rental Platform

Each Pydantic model below represents a MongoDB collection. The collection
name is the lowercase of the class name (e.g., Car -> "car").
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import date


class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    license_no: Optional[str] = Field(None, description="Driver license number")
    is_active: bool = Field(True, description="Whether user is active")


class Car(BaseModel):
    title: str = Field(..., description="Display name, e.g., Tesla Model 3")
    brand: str = Field(..., description="Car brand, e.g., Tesla")
    model: str = Field(..., description="Model name")
    year: int = Field(..., description="Manufacturing year")
    type: str = Field(..., description="Type: sedan, suv, coupe, hatchback, van")
    transmission: str = Field(..., description="manual or automatic")
    fuel_type: str = Field(..., description="petrol, diesel, electric, hybrid")
    seats: int = Field(..., ge=1, le=9, description="Seating capacity")
    luggage: Optional[int] = Field(0, ge=0, description="Luggage capacity")
    price_per_day: float = Field(..., ge=0, description="Rental price per day")
    images: List[str] = Field(default_factory=list, description="Image URLs")
    rating: Optional[float] = Field(4.5, ge=0, le=5)
    featured: bool = Field(False, description="Whether to show on homepage")


class Review(BaseModel):
    car_id: str = Field(..., description="Referenced car id (string)")
    user_name: str = Field(..., description="Reviewer display name")
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class Booking(BaseModel):
    car_id: str = Field(..., description="Car id")
    user_name: str = Field(..., description="Customer name")
    email: EmailStr = Field(..., description="Customer email")
    phone: Optional[str] = None
    pickup_date: date = Field(..., description="Pickup date")
    dropoff_date: date = Field(..., description="Dropoff date (exclusive)")
    pickup_location: Optional[str] = None
    dropoff_location: Optional[str] = None
    total_cost: Optional[float] = Field(None, ge=0)
    status: str = Field("active", description="active, completed, cancelled")


class Favorite(BaseModel):
    user_email: EmailStr
    car_id: str
