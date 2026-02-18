from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Исходные данные пользователей с правильными ID (начиная с 1)
INITIAL_USERS = [
    {"id": "1", "name": "David Bush"},
    {"id": "2", "name": "Mikka Heep"},
    {"id": "3", "name": "Hannah Oberty"},
    {"id": "4", "name": "Petula Jackson"},
    {"id": "5", "name": "Clark Peterson"},
    {"id": "6", "name": "Betty Williamson"},
    {"id": "7", "name": "John Doe"},
    {"id": "8", "name": "John \"Fireman\" Smith"},
    {"id": "9", "name": "Harrison Ford"},
    {"id": "10", "name": "Bob Dowson"}
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

@app.route('/reset', methods=['GET', 'POST'])
def reset():
    """Инициализирует базу пользователей начальным набором данных"""
    global users_db
    users_db = [user.copy() for user in INITIAL_USERS]  # Создаем копии, чтобы не изменять оригинал
    return success_response()

@app.route('/index', methods=['GET'])
def index():
    """Возвращает упорядоченный по id список пользователей"""
    try:
        # Получаем параметры
        offset = request.args.get('offset', '0')
        count = request.args.get('count')
        
        # Валидация offset
        try:
            offset = int(offset)
        except ValueError:
            return error_response("Invalid offset parameter")
        
        if offset < 0:
            return success_response([])  # По спецификации: при отрицательном offset возвращаем пустой результат
        
        # Валидация count если он есть
        if count is not None:
            try:
                count = int(count)
            except ValueError:
                return error_response("Invalid count parameter")
            
            if count < 0:
                return success_response([])  # По спецификации: при отрицательном count возвращаем пустой результат
        else:
            count = None
        
        # Сортируем пользователей по id (как строки, для консистентности)
        sorted_users = sorted(users_db, key=lambda x: x['id'])
        
        # Применяем пагинацию
        if offset >= len(sorted_users):
            return success_response([])
        
        if count is not None:
            # Специфичное поведение: при count=0 возвращаем одного пользователя начиная с offset
            if count == 0:
                result = sorted_users[offset:offset + 1]
            else:
                result = sorted_users[offset:offset + count]
        else:
            result = sorted_users[offset:]
        
        return success_response(result)
        
    except Exception as e:
        return error_response(str(e))

@app.route('/get', methods=['GET'])
def get_user():
    """Возвращает информацию о пользователе с идентификатором ID"""
    try:
        user_id = request.args.get('id')
        if not user_id:
            return error_response("Missing id parameter")
        
        # Ищем пользователя (сравниваем как строки)
        user = next((u for u in users_db if u['id'] == str(user_id)), None)
        
        if user:
            return success_response(user)
        else:
            return error_response(f"User with id {user_id} not found")
            
    except Exception as e:
        return error_response(str(e))

# Маршрут для OpenAPI спецификации (оставляем, так как файл существует)
@app.route('/openapi.yaml')
def openapi_spec():
    """Отдает OpenAPI спецификацию"""
    return send_from_directory('.', 'openapi.yaml')

@app.route('/', methods=['GET'])
def home():
    return success_response({
        "message": "QATest API",
        "version": "1.0.0",
        "description": "API для работы со списком пользователей",
        "endpoints": {
            "GET /reset": "Сброс базы данных к начальному состоянию",
            "GET /index?offset=0&count=10": "Получение списка пользователей с пагинацией",
            "GET /get?id=1": "Получение пользователя по ID"
        },
        "openapi_spec": "/openapi.yaml",
        "current_users": len(users_db),
        "users": users_db if len(users_db) <= 5 else f"{len(users_db)} users available"
    })

if __name__ == '__main__':
    # Инициализация базы при запуске
    users_db = [user.copy() for user in INITIAL_USERS]
    print("🚀 QATest API запущен!")
    print(f"📊 Загружено {len(users_db)} пользователей")
    print("🔗 OpenAPI спецификация: http://127.0.0.1:5000/openapi.yaml")
    print("\n📌 Доступные эндпоинты:")
    print("   GET  /reset")
    print("   GET  /index?offset=0&count=10")
    print("   GET  /get?id=1")
    print("   GET  /")
    app.run(debug=True, host='0.0.0.0', port=5000)
