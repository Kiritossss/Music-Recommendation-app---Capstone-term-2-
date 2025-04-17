# backend/routes/auth.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import os, json

router = APIRouter(tags=["Auth"])

# ======================= CONFIG =======================
SECRET_KEY = "supersecretkey123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_PATH = os.path.join(BASE_DIR, "..", "data", "users.json")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ======================= Ensure File =======================
os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)
if not os.path.exists(USERS_PATH):
    with open(USERS_PATH, "w") as f:
        json.dump({}, f)

# ======================= Models =======================
class User(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# ======================= Auth Helpers =======================
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ======================= Routes =======================
@router.post("/register", summary="Register New User")
def register(user: User):
    user.username = user.username.lower()
    with open(USERS_PATH, "r+") as f:
        users = json.load(f)
        if user.username in users:
            raise HTTPException(status_code=400, detail="Username already exists")
        users[user.username] = get_password_hash(user.password)
        f.seek(0)
        json.dump(users, f, indent=2)
        f.truncate()
    return {"message": "User registered"}

@router.post("/login", response_model=Token, summary="Login & Get Token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    username = form_data.username.lower()
    password = form_data.password
    with open(USERS_PATH, "r") as f:
        users = json.load(f)
        if username not in users or not verify_password(password, users[username]):
            raise HTTPException(status_code=400, detail="Invalid username or password")
    token = create_access_token(data={"sub": username})
    return {"access_token": token, "token_type": "bearer"}

# ======================= Auth Dependency =======================
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ======================= Test Route =======================
@router.get("/test", summary="Test Auth Route", include_in_schema=True)
def test_route():
    return {"message": "YouTube router is working ✅"}
