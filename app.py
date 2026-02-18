from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Исходные данные пользователей
INITIAL_USERS = [
    {"id": "1", "name": "Alice Smith"},
    {"id": "2", "name": "John Doe"},
    {"id": "3", "name": "Buffalo Bill"},
    {"id": "4", "name": "Charlie Brown"},
    {"id": "5", "name": "Diana Prince"}
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
    global users_db
    users_db = INITIAL_USERS.copy()
    return success_response()

@app.route('/index', methods=['GET'])
def index():
    try:
        offset = int(request.args.get('offset', 0))
        count = request.args.get('count')
        
        if offset < 0:
            return error_response("Offset must be non-negative")
        
        sorted_users = sorted(users_db, key=lambda x: x['id'])
        
        if count is not None:
            count = int(count)
            if count < 0:
                return error_response("Count must be non-negative")
            result = sorted_users[offset:offset + count]
        else:
            result = sorted_users[offset:]
        
        return success_response(result)
    except ValueError:
        return error_response("Invalid offset or count parameter")
    except Exception as e:
        return error_response(str(e))

@app.route('/get', methods=['GET'])
def get_user():
    try:
        user_id = request.args.get('id')
        if not user_id:
            return error_response("Missing id parameter")
        
        user = next((u for u in users_db if u['id'] == user_id), None)
        if user:
            return success_response(user)
        else:
            return error_response(f"User with id {user_id} not found")
    except Exception as e:
        return error_response(str(e))

# Маршрут для OpenAPI спецификации
@app.route('/openapi.yaml')
def openapi_spec():
    """Отдает OpenAPI спецификацию"""
    return send_from_directory('.', 'openapi.yaml')

# Маршрут для Swagger UI
@app.route('/swagger.html')
def swagger_ui():
    """Отдает Swagger UI интерфейс"""
    return send_from_directory('.', 'swagger.html')

# Маршрут для документации (короткая ссылка)
@app.route('/docs')
@app.route('/documentation')
def documentation():
    """Редирект на Swagger UI"""
    return swagger_ui()

@app.route('/', methods=['GET'])
def home():
    return success_response({
        "message": "QATest API",
        "version": "1.0.0",
        "documentation": {
            "swagger": "/swagger.html",
            "openapi": "/openapi.yaml",
            "docs": "/docs"
        },
        "endpoints": {
            "/reset": "Reset database to initial state",
            "/index?offset=0&count=10": "List users with pagination",
            "/get?id=1": "Get user by id"
        },
        "users_count": len(users_db)
    })

# Обработчик для статических файлов (если понадобятся дополнительные)
@app.route('/static/<path:filename>')
def static_files(filename):
    """Отдает статические файлы из папки static"""
    return send_from_directory('static', filename)

if __name__ == '__main__':
    # Инициализация базы при запуске
    users_db = INITIAL_USERS.copy()
    print("🚀 QATest API запущен!")
    print("📚 Документация: http://127.0.0.1:5000/docs")
    print("🔗 OpenAPI: http://127.0.0.1:5000/openapi.yaml")
    app.run(debug=True, host='0.0.0.0', port=5000)
