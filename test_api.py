import pytest
import requests
import json
import yaml
from jsonschema import validate, ValidationError
from openapi_schema_validator import OAS30Validator
import time

# Конфигурация
BASE_URL = "http://localhost:5000"  # для локального тестирования
# BASE_URL = "https://qatest-api.onrender.com"  # для тестирования на Render

# Загружаем OpenAPI спецификацию
def load_openapi_spec():
    """Загружает OpenAPI спецификацию из файла"""
    try:
        with open('openapi.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        # Пробуем загрузить с сервера
        response = requests.get(f"{BASE_URL}/openapi.yaml")
        if response.status_code == 200:
            return yaml.safe_load(response.text)
        else:
            raise Exception("Cannot load OpenAPI specification")

OPENAPI_SPEC = load_openapi_spec()

def validate_against_openapi(response_data, path, method, status_code=200):
    """
    Валидирует ответ против OpenAPI спецификации
    """
    # Находим схему для данного path и method
    path_item = OPENAPI_SPEC['paths'].get(path)
    assert path_item, f"Path {path} not found in OpenAPI spec"
    
    operation = path_item.get(method.lower())
    assert operation, f"Method {method} not found for path {path}"
    
    # Находим схему ответа для status_code
    responses = operation.get('responses', {})
    response_spec = responses.get(str(status_code))
    
    # Особый случай: для ошибок может быть несколько примеров
    if status_code == 200 and response_data.get('status') == 'error':
        # Ищем схему для ошибки (может быть под другим ключом)
        for key, spec in responses.items():
            if key.startswith('200') and 'error' in key:
                response_spec = spec
                break
    
    assert response_spec, f"Response spec for {path} {method} {status_code} not found"
    
    # Получаем схему из response_spec
    content = response_spec.get('content', {})
    schema = content.get('application/json', {}).get('schema')
    
    if not schema:
        # Если нет явной схемы, используем пример для валидации
        example = response_spec.get('content', {}).get('application/json', {}).get('example')
        if example:
            # Простая проверка структуры по примеру
            assert response_data.keys() == example.keys(), f"Response structure mismatch. Expected {example.keys()}, got {response_data.keys()}"
            return
    
    # Валидируем по схеме
    validator = OAS30Validator(schema)
    errors = list(validator.iter_errors(response_data))
    
    if errors:
        error_messages = [f"{e.path}: {e.message}" for e in errors]
        raise AssertionError(f"Validation failed:\n" + "\n".join(error_messages))

class TestQATestAPI:
    """Набор тестов для QATest API с валидацией по OpenAPI"""

    def setup_method(self):
        """Сбрасываем базу данных перед каждым тестом"""
        response = requests.post(f"{BASE_URL}/reset")
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/reset', 'post')

    # ===== ТЕСТЫ ДЛЯ POST /reset =====
    
    def test_reset_returns_ok(self):
        """Проверяет, что POST /reset возвращает статус OK"""
        response = requests.post(f"{BASE_URL}/reset")
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/reset', 'post')

    # ===== ТЕСТЫ ДЛЯ GET /users =====
    
    def test_get_users_default_pagination(self):
        """Проверяет GET /users с параметрами по умолчанию"""
        response = requests.get(f"{BASE_URL}/users")
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users', 'get')
        
        result = data["result"]
        assert isinstance(result, list)
        assert len(result) == 10
        
        # Проверяем сортировку по id
        ids = [user["id"] for user in result]
        assert ids == sorted(ids)

    def test_get_users_with_offset_and_count(self):
        """Проверяет GET /users с offset и count"""
        response = requests.get(f"{BASE_URL}/users?offset=2&count=4")
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users', 'get')
        
        result = data["result"]
        assert len(result) == 4
        assert result[0]["id"] == 3
        assert result[-1]["id"] == 6

    def test_get_users_offset_beyond_limit(self):
        """Проверяет GET /users с offset больше количества пользователей"""
        response = requests.get(f"{BASE_URL}/users?offset=20")
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users', 'get')
        assert data["result"] == []

    def test_get_users_invalid_offset(self):
        """Проверяет GET /users с некорректным offset"""
        response = requests.get(f"{BASE_URL}/users?offset=-5")
        assert response.status_code == 200
        data = response.json()
        # Должен вернуть пустой результат, а не ошибку
        validate_against_openapi(data, '/users', 'get')
        assert data["result"] == []

    def test_get_users_invalid_params_type(self):
        """Проверяет GET /users с параметрами неверного типа"""
        response = requests.get(f"{BASE_URL}/users?offset=abc&count=def")
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users', 'get')

    # ===== ТЕСТЫ ДЛЯ POST /users =====
    
    def test_create_user_with_name(self):
        """Проверяет создание пользователя с именем"""
        new_user = {
            "name": "Test User",
            "msisdn": "79998887766"
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users', 'post')
        
        result = data["result"]
        assert result["name"] == "Test User"
        assert result["msisdn"] == "79998887766"
        assert isinstance(result["id"], int)

    def test_create_user_without_name(self):
        """Проверяет создание пользователя без имени"""
        new_user = {
            "msisdn": "79998887755"
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users', 'post')
        
        result = data["result"]
        assert result["name"] is None
        assert result["msisdn"] == "79998887755"

    def test_create_user_missing_msisdn(self):
        """Проверяет ошибку при создании без обязательного поля msisdn"""
        new_user = {
            "name": "Test User"
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users', 'post')
        assert "Missing required field" in data["description"]

    def test_create_user_duplicate_msisdn(self):
        """Проверяет ошибку при создании с существующим msisdn"""
        new_user = {
            "msisdn": "79161234001"  # Уже существует
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users', 'post')
        assert "already exists" in data["description"]

    def test_create_user_name_too_long(self):
        """Проверяет ошибку при слишком длинном имени"""
        new_user = {
            "name": "A" * 31,
            "msisdn": "79998887744"
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users', 'post')
        assert "must not exceed 30 characters" in data["description"]

    def test_create_user_invalid_msisdn_length(self):
        """Проверяет ошибку при неверной длине MSISDN"""
        response = requests.post(f"{BASE_URL}/users", json={
            "msisdn": "1234567890"  # 10 цифр
        })
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users', 'post')
        assert "exactly 11 digits" in data["description"]

    def test_create_user_extra_fields(self):
        """Проверяет ошибку при передаче лишних полей"""
        new_user = {
            "name": "Test User",
            "msisdn": "79998887733",
            "extra_field": "should not be here"
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users', 'post')
        assert "Extra fields not allowed" in data["description"]

    # ===== ТЕСТЫ ДЛЯ GET /users/{id} =====
    
    def test_get_user_by_id(self):
        """Проверяет получение существующего пользователя по ID"""
        response = requests.get(f"{BASE_URL}/users/5")
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users/{id}', 'get')
        
        user = data["result"]
        assert user["id"] == 5
        assert user["name"] == "Clark Peterson"
        assert user["msisdn"] == "79161234005"

    def test_get_user_not_found(self):
        """Проверяет ошибку при запросе несуществующего пользователя"""
        response = requests.get(f"{BASE_URL}/users/999")
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users/{id}', 'get')
        assert "not found" in data["description"]

    # ===== ТЕСТЫ ДЛЯ DELETE /users/{id} =====
    
    def test_delete_user(self):
        """Проверяет удаление существующего пользователя"""
        # Создаем пользователя
        create_response = requests.post(f"{BASE_URL}/users", json={
            "msisdn": "79998887722"
        })
        user_id = create_response.json()["result"]["id"]
        
        # Удаляем его
        delete_response = requests.delete(f"{BASE_URL}/users/{user_id}")
        assert delete_response.status_code == 200
        data = delete_response.json()
        validate_against_openapi(data, '/users/{id}', 'delete')
        assert "deleted successfully" in data["result"]["message"]

    def test_delete_user_not_found(self):
        """Проверяет ошибку при удалении несуществующего пользователя"""
        response = requests.delete(f"{BASE_URL}/users/999")
        assert response.status_code == 200
        data = response.json()
        validate_against_openapi(data, '/users/{id}', 'delete')
        assert "not found" in data["description"]

    # ===== ТЕСТЫ НА СООТВЕТСТВИЕ СПЕЦИФИКАЦИИ =====
    
    def test_all_endpoints_return_200(self):
        """Проверяет, что все эндпоинты возвращают HTTP 200"""
        endpoints = [
            ('post', '/reset'),
            ('get', '/users'),
            ('post', '/users'),
            ('get', '/users/1'),
            ('delete', '/users/1'),
        ]
        
        for method, path in endpoints:
            if method == 'get':
                response = requests.get(f"{BASE_URL}{path}")
            elif method == 'post':
                if path == '/users':
                    response = requests.post(f"{BASE_URL}{path}", json={"msisdn": "79998887711"})
                else:
                    response = requests.post(f"{BASE_URL}{path}")
            elif method == 'delete':
                response = requests.delete(f"{BASE_URL}{path}")
            
            assert response.status_code == 200, f"{method.upper()} {path} вернул {response.status_code}"
            validate_against_openapi(response.json(), path, method)

    def test_response_structure_against_openapi(self):
        """Массовая проверка структуры ответов против OpenAPI"""
        test_cases = [
            # Успешные запросы
            ('get', '/users', None),
            ('get', '/users?offset=2&count=3', None),
            ('get', '/users/1', None),
            ('post', '/users', {"msisdn": "79998887799"}),
            
            # Запросы с ошибками
            ('get', '/users/999', None),
            ('post', '/users', {}),
            ('post', '/users', {"msisdn": "invalid"}),
            ('delete', '/users/999', None),
        ]
        
        for method, path, body in test_cases:
            if method == 'get':
                response = requests.get(f"{BASE_URL}{path}")
            elif method == 'post':
                response = requests.post(f"{BASE_URL}{path}", json=body)
            elif method == 'delete':
                response = requests.delete(f"{BASE_URL}{path}")
            
            try:
                validate_against_openapi(response.json(), path.split('?')[0], method)
                print(f"✅ {method.upper()} {path} - OK")
            except AssertionError as e:
                print(f"❌ {method.upper()} {path} - FAIL")
                print(f"   {str(e)}")
                raise

    def test_user_schema_validation(self):
        """Проверяет, что все пользователи соответствуют схеме User из OpenAPI"""
        response = requests.get(f"{BASE_URL}/users")
        users = response.json()["result"]
        
        # Получаем схему User из OpenAPI
        user_schema = OPENAPI_SPEC['components']['schemas']['User']
        validator = OAS30Validator(user_schema)
        
        for user in users:
            errors = list(validator.iter_errors(user))
            assert not errors, f"User validation failed: {errors}"

    def test_error_response_schema(self):
        """Проверяет схему ответа с ошибкой"""
        response = requests.get(f"{BASE_URL}/users/999")
        data = response.json()
        
        # Получаем схему ErrorResponse из OpenAPI
        error_schema = OPENAPI_SPEC['components']['schemas']['ErrorResponse']
        validator = OAS30Validator(error_schema)
        
        errors = list(validator.iter_errors(data))
        assert not errors, f"Error response validation failed: {errors}"

# ===== ТЕСТЫ ДЛЯ ПРОВЕРКИ САМОЙ OPENAPI СПЕЦИФИКАЦИИ =====

def test_openapi_spec_is_valid():
    """Проверяет, что OpenAPI спецификация валидна"""
    # Базовая проверка наличия обязательных полей
    assert 'openapi' in OPENAPI_SPEC
    assert 'info' in OPENAPI_SPEC
    assert 'paths' in OPENAPI_SPEC
    
    # Проверяем все эндпоинты
    expected_paths = ['/reset', '/users', '/users/{id}']
    for path in expected_paths:
        assert path in OPENAPI_SPEC['paths'], f"Path {path} not found in spec"
    
    # Проверяем схемы
    expected_schemas = ['User', 'UserInput', 'UserList', 'SuccessResponse', 'ErrorResponse', 'CreateUserResponse']
    schemas = OPENAPI_SPEC['components']['schemas']
    for schema in expected_schemas:
        assert schema in schemas, f"Schema {schema} not found in spec"

if __name__ == "__main__":
    pytest.main(["-v", "--tb=short", __file__])
