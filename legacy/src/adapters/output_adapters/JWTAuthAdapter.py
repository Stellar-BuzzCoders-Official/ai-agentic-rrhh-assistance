from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import os
import logging

logger = logging.getLogger(__name__)

class JWTAuthAdapter:
    def __init__(self):
        self.secret_key = os.getenv('JWT_SECRET_KEY')
        self.algorithm = "HS256"
        self.access_token_expire_minutes = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES'))
        logger.info("Inicializando JWTAuthAdapter con configuración de seguridad")
        logger.info("access_token_expire_minutes: %d", self.access_token_expire_minutes)
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifica si la contraseña en texto plano coincide con el hash"""
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Error al verificar contraseña: {str(e)}")
            return False
    
    def hash_password(self, password: str) -> str:
        """Genera un hash de la contraseña"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Crea un token JWT de acceso"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        
        try:
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            logger.info(f"Token JWT creado exitosamente para usuario: {data.get('sub', 'unknown')}")
            logger.debug(f"Token expira en: {expire} UTC")
            return encoded_jwt
        except Exception as e:
            logger.error(f"Error al crear token JWT: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al generar token de acceso"
            )
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verifica y decodifica un token JWT"""
        try:
            # jwt.decode() ya maneja automáticamente la verificación de expiración
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id: str = payload.get("sub")
            
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token inválido: no se encontró el usuario",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # REMOVIDO: La verificación manual redundante de expiración
            # jwt.decode() ya se encarga de esto automáticamente
            
            logger.info(f"Token verificado exitosamente para usuario: {user_id}")
            logger.debug(f"Token válido hasta: {datetime.fromtimestamp(payload.get('exp', 0))}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Intento de acceso con token expirado")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token inválido: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error(f"Error inesperado al verificar token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al verificar token"
            )
    
    def authenticate_user(self, mongo_repo, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Autentica un usuario con username y password"""
        try:
            # CORRECCIÓN: Buscar por 'userName' en lugar de 'username'
            user = mongo_repo.find_one("users", {"userName": username})
            
            if not user:
                logger.warning(f"Intento de login con usuario inexistente: {username}")
                return None
            
            # Verificar contraseña
            if not self.verify_password(password, user.get("password", "")):
                logger.warning(f"Intento de login con contraseña incorrecta para usuario: {username}")
                return None
            
            logger.info(f"Usuario autenticado exitosamente: {username}")
            
            # Retornar datos del usuario sin la contraseña
            user_data = {
                "_id": str(user["_id"]),
                "username": user["userName"],  # Usar el campo correcto
                "email": user.get("email"),
                "userID": user.get("userID"),
                "firstName": user.get("firstName"),  # Corregir el typo
                "lastName": user.get("lastName"),
                "created_at": user.get("created_at"),
                "is_active": user.get("is_active", True)
            }
            
            return user_data
            
        except Exception as e:
            logger.error(f"Error al autenticar usuario {username}: {str(e)}")
            return None
    
    def create_login_response(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea la respuesta completa de login con token y datos del usuario"""
        try:
            # Crear payload para el token
            token_data = {
                "sub": user_data["userID"],  # subject (identificador del usuario)
                "username": user_data["username"],
                "email": user_data.get("email")
            }
            
            # Generar token
            access_token = self.create_access_token(data=token_data)
            
            # Crear respuesta
            response = {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": self.access_token_expire_minutes * 60,  # en segundos
                "user": {
                    "id": user_data["_id"],
                    "userID": user_data["userID"],
                    "username": user_data["username"],
                    "email": user_data.get("email"),
                    "is_active": user_data.get("is_active", True)
                }
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error al crear respuesta de login: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al generar respuesta de login"
            )