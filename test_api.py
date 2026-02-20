import pytest
import requests
import json
import yaml
from jsonschema import validate, ValidationError
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
        try:
            response = requests.get(f"{BASE_URL}/openapi.yaml")
            if response.status_code == 200:
                return yaml.safe_load(response.text)
        except:
            pass
    return None

OPENAPI_SPEC = load_openapi_spec()

# Простые схемы для валидации (на случай, если OpenAPI не загрузится)
SIMPLE_USER_SCHEMA = {
    "type": "object",
    "required": ["id", "msisdn"],
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": ["string", "null"], "maxLength": 30},
        "msisdn": {"type": "string", "pattern": "^\\d{11}$"}
    }
}

SIMPLE_SUCCESS_SCHEMA = {
    "type": "object",
    "required": ["status"],
    "properties": {
        "status": {"type": "string", "enum": ["OK"]},
        "result": {"type": ["object", "array", "null"]}
    }
}

SIMPLE_ERROR_SCHEMA = {
    "type": "object",
    "required": ["status", "description"],
    "properties": {
        "status": {"type": "string", "enum": ["error"]},
        "description": {"type": "string"}
    }
}

def validate_against_schema(data, expected_schema):
    """Простая валидация по схеме"""
    try:
        validate(instance=data, schema=expected_schema)
        return True, None
    except ValidationError as e:
        return False, str(e)

class TestQATestAPI:
    """Набор тестов для QATest API"""

    def setup_method(self):
        """Сбрасываем базу данных перед каждым тестом"""
        max_retries = 3
        for i in range(max_retries):
            try:
                response = requests.post(f"{BASE_URL}/reset", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    assert data["status"] == "OK"
                    return
            except requests.exceptions.RequestException:
                if i == max_retries - 1:
                    raise
                time.sleep(2)

    # ===== ТЕСТЫ ДЛЯ POST /reset =====
    
    def test_reset_returns_ok(self):
        """Проверяет, что POST /reset возвращает статус OK"""
        response = requests.post(f"{BASE_URL}/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "OK"
        valid, error = validate_against_schema(data, SIMPLE_SUCCESS_SCHEMA)
        assert valid, f"Schema validation failed: {error}"

    # ===== ТЕСТЫ ДЛЯ GET /users =====
    
    def test_get_users_default_pagination(self):
        """Проверяет GET /users с параметрами по умолчанию"""
        response = requests.get(f"{BASE_URL}/users")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "OK"
        
        result = data["result"]
        assert isinstance(result, list)
        assert len(result) == 10
        
        for user in result:
            valid, error = validate_against_schema(user, SIMPLE_USER_SCHEMA)
            assert valid, f"User validation failed: {error}"
        
        ids = [user["id"] for user in result]
        assert ids == sorted(ids)

    def test_get_users_with_offset_and_count(self):
        """Проверяет GET /users с offset и count"""
        response = requests.get(f"{BASE_URL}/users?offset=2&count=4")
        assert response.status_code == 200
        data = response.json()
        
        result = data["result"]
        assert len(result) == 4
        assert result[0]["id"] == 3
        assert result[-1]["id"] == 6

    def test_get_users_offset_beyond_limit(self):
        """Проверяет GET /users с offset больше количества пользователей"""
        response = requests.get(f"{BASE_URL}/users?offset=20")
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == []

    def test_get_users_invalid_offset(self):
        """Проверяет GET /users с некорректным offset"""
        response = requests.get(f"{BASE_URL}/users?offset=-5")
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == []

    def test_get_users_invalid_params_type(self):
        """Проверяет GET /users с параметрами неверного типа"""
        response = requests.get(f"{BASE_URL}/users?offset=abc&count=def")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        valid, error = validate_against_schema(data, SIMPLE_ERROR_SCHEMA)
        assert valid, f"Error schema validation failed: {error}"

    def test_get_users_count_zero(self):
        """Проверяет специальное поведение: count=0 возвращает одного пользователя"""
        response = requests.get(f"{BASE_URL}/users?offset=3&count=0")
        assert response.status_code == 200
        data = response.json()
        
        result = data["result"]
        assert len(result) == 1
        assert result[0]["id"] == 4

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
        
        assert data["status"] == "OK"
        result = data["result"]
        assert result["name"] == "Test User"
        assert result["msisdn"] == "79998887766"
        assert isinstance(result["id"], int)
        
        # Проверяем, что пользователь действительно создан
        get_response = requests.get(f"{BASE_URL}/users/{result['id']}")
        assert get_response.status_code == 200
        user_data = get_response.json()
        assert user_data["result"]["name"] == "Test User"

    def test_create_user_without_name(self):
        """Проверяет создание пользователя без имени"""
        new_user = {
            "msisdn": "79998887755"
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        
        result = data["result"]
        assert result["name"] is None
        assert result["msisdn"] == "79998887755"
        assert isinstance(result["id"], int)

    def test_create_user_missing_msisdn(self):
        """Проверяет ошибку при создании без обязательного поля msisdn"""
        new_user = {
            "name": "Test User"
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Missing required field" in data["description"]

    def test_create_user_duplicate_msisdn(self):
        """Проверяет ошибку при создании с существующим msisdn"""
        new_user = {
            "msisdn": "79161234001"
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
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
        assert data["status"] == "error"
        assert "must not exceed 30 characters" in data["description"]

    def test_create_user_invalid_msisdn_length(self):
        """Проверяет ошибку при неверной длине MSISDN"""
        # Слишком короткий
        response = requests.post(f"{BASE_URL}/users", json={
            "msisdn": "1234567890"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "exactly 11 digits" in data["description"]
        
        # Слишком длинный
        response = requests.post(f"{BASE_URL}/users", json={
            "msisdn": "123456789012"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "exactly 11 digits" in data["description"]

    def test_create_user_msisdn_with_letters(self):
        """Проверяет ошибку при MSISDN с буквами"""
        new_user = {
            "msisdn": "7916abc4567"
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "contain only digits" in data["description"]

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
        assert data["status"] == "error"
        assert "Extra fields not allowed" in data["description"]

    # ===== ТЕСТЫ ДЛЯ GET /users/{id} =====
    
    def test_get_user_by_id(self):
        """Проверяет получение существующего пользователя по ID"""
        response = requests.get(f"{BASE_URL}/users/5")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "OK"
        user = data["result"]
        valid, error = validate_against_schema(user, SIMPLE_USER_SCHEMA)
        assert valid, f"User validation failed: {error}"
        assert user["id"] == 5
        assert user["name"] == "Clark Peterson"
        assert user["msisdn"] == "79161234005"

    def test_get_user_not_found(self):
        """Проверяет ошибку при запросе несуществующего пользователя"""
        response = requests.get(f"{BASE_URL}/users/999")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "not found" in data["description"]

    # ===== ТЕСТЫ ДЛЯ DELETE /users/{id} =====
    
    def test_delete_user(self):
        """Проверяет удаление существующего пользователя"""
        create_response = requests.post(f"{BASE_URL}/users", json={
            "msisdn": "79998887722"
        })
        user_id = create_response.json()["result"]["id"]
        
        delete_response = requests.delete(f"{BASE_URL}/users/{user_id}")
        assert delete_response.status_code == 200
        data = delete_response.json()
        assert data["status"] == "OK"
        assert "deleted successfully" in data["result"]["message"]
        
        get_response = requests.get(f"{BASE_URL}/users/{user_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "error"

    def test_delete_user_not_found(self):
        """Проверяет ошибку при удалении несуществующего пользователя"""
        response = requests.delete(f"{BASE_URL}/users/999")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "not found" in data["description"]

    # ===== ТЕСТЫ НА СООТВЕТСТВИЕ СПЕЦИФИКАЦИИ =====
    
    def test_all_responses_have_status_200(self):
        """Проверяет, что все ответы приходят с HTTP статусом 200"""
        endpoints = [
            ("POST", "/reset"),
            ("GET", "/users"),
            ("GET", "/users?offset=2&count=3"),
            ("GET", "/users/1"),
            ("DELETE", "/users/1"),
            ("POST", "/users"),
        ]
        
        for method, url in endpoints:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{url}")
            elif method == "POST":
                if url == "/users":
                    response = requests.post(f"{BASE_URL}{url}", json={"msisdn": "79998887711"})
                else:
                    response = requests.post(f"{BASE_URL}{url}")
            elif method == "DELETE":
                response = requests.delete(f"{BASE_URL}{url}")
            
            assert response.status_code == 200, f"{method} {url} вернул {response.status_code}"

    def test_user_data_validation(self):
        """Проверяет, что все пользователи соответствуют схеме"""
        response = requests.get(f"{BASE_URL}/users")
        users = response.json()["result"]
        
        for user in users:
            valid, error = validate_against_schema(user, SIMPLE_USER_SCHEMA)
            assert valid, f"User validation failed: {error}"
            assert len(user["msisdn"]) == 11
            assert user["msisdn"].isdigit()
            if user["name"] is not None:
                assert len(user["name"]) <= 30

    def test_msisdn_uniqueness(self):
        """Проверяет уникальность MSISDN"""
        response = requests.get(f"{BASE_URL}/users")
        users = response.json()["result"]
        msisdns = [u["msisdn"] for u in users]
        assert len(msisdns) == len(set(msisdns))

    def test_id_auto_increment(self):
        """Проверяет автоинкремент ID"""
        response = requests.get(f"{BASE_URL}/users")
        max_id = max(u["id"] for u in response.json()["result"])
        
        create_response = requests.post(f"{BASE_URL}/users", json={
            "msisdn": "79998887700"
        })
        new_id = create_response.json()["result"]["id"]
        
        assert new_id > max_id

    def test_pagination_consistency(self):
        """Проверяет согласованность пагинации"""
        all_response = requests.get(f"{BASE_URL}/users")
        all_users = all_response.json()["result"]
        
        page1 = requests.get(f"{BASE_URL}/users?offset=0&count=3").json()["result"]
        page2 = requests.get(f"{BASE_URL}/users?offset=3&count=3").json()["result"]
        page3 = requests.get(f"{BASE_URL}/users?offset=6&count=3").json()["result"]
        
        combined = page1 + page2 + page3
        assert combined == all_users[:9]

# ===== ТЕСТЫ ДЛЯ ПРОВЕРКИ OPENAPI СПЕЦИФИКАЦИИ =====

def test_openapi_spec_exists():
    """Проверяет, что OpenAPI спецификация существует"""
    assert OPENAPI_SPEC is not None, "OpenAPI spec not found"

def test_openapi_spec_is_valid():
    """Проверяет, что OpenAPI спецификация содержит основные разделы"""
    if OPENAPI_SPEC:
        assert 'openapi' in OPENAPI_SPEC
        assert 'info' in OPENAPI_SPEC
        assert 'paths' in OPENAPI_SPEC
        
        expected_paths = ['/reset', '/users', '/users/{id}']
        for path in expected_paths:
            assert path in OPENAPI_SPEC['paths'], f"Path {path} not found in spec"

if __name__ == "__main__":
    pytest.main(["-v", "--tb=short", __file__])
