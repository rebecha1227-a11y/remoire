from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import API_SECRET_KEY

bearer_scheme = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)):
    if credentials.credentials != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="无效的 token")
    return credentials.credentials
