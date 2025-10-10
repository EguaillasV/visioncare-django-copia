import json
import random
import string
import httpx

API = "http://127.0.0.1:8001/api"


def generar_cedula_valida():
    # Genera una cédula válida (provincia 01-24, tercer dígito < 6)
    provincia = random.randint(1, 24)
    d = [int(x) for x in f"{provincia:02d}"]
    d.append(random.randint(0, 5))
    while len(d) < 9:
        d.append(random.randint(0, 9))
    coef = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0
    for i in range(9):
        prod = d[i] * coef[i]
        if prod >= 10:
            prod -= 9
        total += prod
    verificador = (10 - (total % 10)) % 10
    d.append(verificador)
    return "".join(str(x) for x in d)


def main():
    email = f"test{random.randint(10000,99999)}@example.com"
    payload = {
        "email": email,
        "username": email,
        "first_name": "Test",
        "last_name": "User",
        "password": "Aa123456!",
        "password_confirm": "Aa123456!",
        "age": 25,
        "cedula": generar_cedula_valida(),
        "gender": "male",
        "phone": "+593900000000",
        "address": "La Troncal",
        "country": "Ecuador",
        "state": "Cañar",
        "city": "La Troncal",
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{API}/auth/register/", json=payload)
        print("STATUS:", r.status_code)
        try:
            print(json.dumps(r.json(), ensure_ascii=False, indent=2))
        except Exception:
            print(r.text)


if __name__ == "__main__":
    main()
