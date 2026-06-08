from core.security import (
    hash_password,
    verify_password,
    create_access_token
)

password = "Password123"

hashed = hash_password(password)

print(hashed)

print(
    verify_password(
        password,
        hashed
    )
)

token = create_access_token(
    {"sub": "admin@test.com"}
)

print(token)