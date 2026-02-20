from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)

# Константы для валидации
MAX_NAME_LENGTH = 30
MSISDN_LENGTH = 11

# Исходные данные пользователей (id как integer)
INITIAL_USERS = [
    {"id": 1, "name": "David Bush", "msisdn": "79161234001"},
    {"id": 2, "name": "Mikka Heep", "msisdn": "79161234002"},
    {"id": 3, "name": "Hannah Oberty", "msisdn": "79161234003"},
    {"id": 4, "name": "Petula Jackson", "msisdn": "79161234004"},
    {"id": 5, "name": "Clark Peterson", "msisdn": "79161234005"},
    {"id": 6, "name": "Betty Williamson", "msisdn": "79161234006"},
    {"id": 7, "name": "John Doe", "msisdn": "79161234007"},
    {"id": 8, "name": "John \"Fireman\" Smith", "msisdn": "79161234008"},
    {"id": 9, "name": "Harrison Ford", "msisdn": "79161234009"},
    {"id": 10, "name": "Bob Dowson", "msisdn": "79161234010"}
]

# Хранилище данных
users_db = []

def success_response(data=None):
    response = {"status": "OK"}
    if data is not None:
        response["result"] = data
    return jsonify(response), 200

def error_response(description):
    return jsonify({
        "status": "error",
        "description": description
    }), 200


# ========== БАГ 1: Граничные значения (Boundary Value Analysis) ==========
# Неправильная валидация максимальной длины имени
def validate_name(name):
    """Проверяет имя (если указано, не длиннее MAX_NAME_LENGTH)"""
    if name is None:
        return True, None
    
    if not isinstance(name, str):
        return False, "Name must be a string"
    
    name = name.strip()
    # БАГ: используется >= вместо > (допускает имена длиной 31 символ)
    if name and len(name) >= MAX_NAME_LENGTH:
        return False, f"Name must not exceed {MAX_NAME_LENGTH} characters"
    
    return True, name if name else None


# ========== БАГ 2: Классы эквивалентности (Equivalence Partitioning) ==========
# Отсутствует проверка формата MSISDN (буквы разрешены)
def validate_msisdn(msisdn):
    """Проверяет MSISDN (ровно 11 цифр)"""
    if not msisdn or not isinstance(msisdn, str):
        return False, "MSISDN is required and must be a string"
    
    msisdn = msisdn.strip()
    
    # БАГ: забыли проверить, что это только цифры!
    # if not msisdn.isdigit():
    #     return False, "MSISDN must contain only digits"
    
    if len(msisdn) != MSISDN_LENGTH:
        return False, f"MSISDN must be exactly {MSISDN_LENGTH} digits"
    
    return True, msisdn


def is_msisdn_unique(msisdn):
    """Проверяет уникальность MSISDN"""
    return not any(user['msisdn'] == msisdn for user in users_db)


# ========== БАГ 3: Попарное тестирование (Pairwise Testing) ==========
# ========== БАГ 10: Отсутствие санитизации query params ==========
@app.route('/users', methods=['GET'])
def get_users():
    """GET /users - возвращает упорядоченный по id список пользователей"""
    try:
        # Получаем параметры
        offset = request.args.get('offset', '0')
        count = request.args.get('count')
        
        # БАГ 10: нет проверки, что offset действительно число перед int()
        # Можно передать offset="abc" и получить 500 ошибку
        offset = int(offset)
        
        if offset < 0:
            return success_response([])
        
        if count is not None:
            # Тот же баг для count
            count = int(count)
            
            if count < 0:
                return success_response([])
        else:
            count = None
        
        # Сортируем пользователей по id
        sorted_users = sorted(users_db, key=lambda x: x['id'])
        
        if offset >= len(sorted_users):
            return success_response([])
        
        if count is not None:
            # БАГ 3: при offset > 0 и count = 0 возвращает неправильного пользователя
            if count == 0:
                # Всегда возвращает первого пользователя, независимо от offset
                result = sorted_users[0:1]
            else:
                result = sorted_users[offset:offset + count]
        else:
            result = sorted_users[offset:]
        
        return success_response(result)
        
    except Exception as e:
        # БАГ 10: при ошибке возвращаем 500 вместо 200 с описанием
        return jsonify({
            "status": "error",
            "description": str(e)
        }), 500


@app.route('/reset', methods=['POST'])
def reset():
    """POST /reset - инициализирует базу пользователей начальным набором данных"""
    global users_db
    users_db = [user.copy() for user in INITIAL_USERS]
    return success_response()


# ========== БАГ 4: Причина-следствие (Cause-Effect) ==========
# ========== БАГ 6: Состояние и переходы (State Transition) ==========
# ========== БАГ 7: Синтаксический анализ (Syntax Testing) ==========
@app.route('/users', methods=['POST'])
def create_user():
    """POST /users - создание нового пользователя"""
    try:
        data = request.get_json()
        
        if not data:
            return error_response("Invalid JSON data")
        
        # Проверяем лишние поля
        allowed_fields = {'name', 'msisdn'}
        received_fields = set(data.keys())
        extra_fields = received_fields - allowed_fields
        
        if extra_fields:
            return error_response(f"Extra fields not allowed: {', '.join(extra_fields)}")
        
        # Проверяем обязательное поле msisdn
        if 'msisdn' not in data:
            return error_response("Missing required field: msisdn")
        
        # Валидация MSISDN
        is_valid_msisdn, msisdn_result = validate_msisdn(data['msisdn'])
        if not is_valid_msisdn:
            return error_response(msisdn_result)
        msisdn = msisdn_result
        
        # БАГ 4: пропущена проверка уникальности MSISDN
        # if not is_msisdn_unique(msisdn):
        #     return error_response(f"User with msisdn {msisdn} already exists")
        
        # Валидация имени (опционально)
        name = None
        if 'name' in data:
            is_valid_name, name_result = validate_name(data['name'])
            if not is_valid_name:
                return error_response(name_result)
            name = name_result
        
        # БАГ 6: ID генерируется неправильно (использует длину, а не максимальный ID)
        # При удалении пользователя ID может повториться
        next_id = len(users_db) + 1
        
        # Создаем нового пользователя
        new_user = {
            "id": next_id,
            "name": name,
            "msisdn": msisdn
        }
        
        users_db.append(new_user)
        
        # БАГ 7: неправильная структура JSON ответа (поле "user" вместо "result")
        return jsonify({
            "status": "OK",
            "user": {
                "id": new_user['id'],
                "name": new_user['name'],
                "msisdn": new_user['msisdn'],
                "message": "User created successfully"
            }
        }), 200
        
    except Exception as e:
        return error_response(str(e))


# ========== БАГ 7 (продолжение): Синтаксический анализ ==========
@app.route('/users/<int:id>', methods=['GET'])
def get_user(id):
    """GET /users/{id} - возвращает информацию о пользователе"""
    try:
        user = next((u for u in users_db if u['id'] == id), None)
        
        if user:
            # БАГ 7: неправильная структура ответа (поле "user" вместо "result")
            return jsonify({
                "status": "OK",
                "user": user
            }), 200
        else:
            return error_response(f"User with id {id} not found")
            
    except Exception as e:
        return error_response(str(e))


@app.route('/users/<int:id>', methods=['DELETE'])
def delete_user(id):
    """DELETE /users/{id} - удаление пользователя"""
    try:
        global users_db
        user = next((u for u in users_db if u['id'] == id), None)
        
        if not user:
            return error_response(f"User with id {id} not found")
        
        users_db = [u for u in users_db if u['id'] != id]
        
        return success_response({
            "message": f"User with id {id} deleted successfully"
        })
        
    except Exception as e:
        return error_response(str(e))


# Маршрут для OpenAPI спецификации
@app.route('/openapi.yaml')
def openapi_spec():
    """Отдает OpenAPI спецификацию"""
    return send_from_directory('.', 'openapi.yaml')


if __name__ == '__main__':
    users_db = [user.copy() for user in INITIAL_USERS]
    print("🚀 QATest API (версия с багами) запущен!")
    print(f"📊 Загружено {len(users_db)} пользователей")
    print("\n📌 Доступные эндпоинты:")
    print("   POST /reset")
    print("   GET  /users?offset=0&count=10")
    print("   POST /users (JSON: msisdn, name - опционально)")
    print("   GET  /users/{id}")
    print("   DELETE /users/{id}")
    print(f"\n🔗 OpenAPI: http://127.0.0.1:5000/openapi.yaml")
    app.run(debug=True, host='0.0.0.0', port=5000)
