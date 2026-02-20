import pytest
import requests
import json
from jsonschema import validate, ValidationError
import time

# Конфигурация
BASE_URL = "http://localhost:5000"  # для локального тестирования
# BASE_URL = "https://qatest-api.onrender.com"  # для тестирования на Render

# Схемы для валидации ответов
user_schema = {
    "type": "object",
    "required": ["id", "msisdn"],
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": ["string", "null"], "maxLength": 30},
        "msisdn": {"type": "string", "pattern": "^\\d{11}$"}
    }
}

success_response_schema = {
    "type": "object",
    "required": ["status"],
    "properties": {
        "status": {"type": "string", "enum": ["OK"]},
        "result": {"type": ["object", "array", "null"]}
    }
}

error_response_schema = {
    "type": "object",
    "required": ["status", "description"],
    "properties": {
        "status": {"type": "string", "enum": ["error"]},
        "description": {"type": "string"}
    }
}

class TestQATestAPI:
    """Набор тестов для QATest API"""

    def setup_method(self):
        """Сбрасываем базу данных перед каждым тестом"""
        response = requests.post(f"{BASE_URL}/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "OK"

    # ===== ТЕСТЫ ДЛЯ POST /reset =====
    
    def test_reset_returns_ok(self):
        """Проверяет, что POST /reset возвращает статус OK"""
        response = requests.post(f"{BASE_URL}/reset")
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=success_response_schema)
        assert data["status"] == "OK"

    # ===== ТЕСТЫ ДЛЯ GET /users =====
    
    def test_get_users_default_pagination(self):
        """Проверяет GET /users с параметрами по умолчанию"""
        response = requests.get(f"{BASE_URL}/users")
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=success_response_schema)
        
        result = data["result"]
        assert isinstance(result, list)
        assert len(result) == 10  # В INITIAL_USERS 10 пользователей
        
        # Проверяем структуру каждого пользователя
        for user in result:
            validate(instance=user, schema=user_schema)
        
        # Проверяем сортировку по id
        ids = [user["id"] for user in result]
        assert ids == sorted(ids)

    def test_get_users_with_offset(self):
        """Проверяет GET /users с параметром offset"""
        # Получаем пользователей начиная с offset=5
        response = requests.get(f"{BASE_URL}/users?offset=5")
        assert response.status_code == 200
        data = response.json()
        
        result = data["result"]
        assert len(result) == 5  # Должно быть 5 пользователей (id 6-10)
        assert result[0]["id"] == 6
        assert result[-1]["id"] == 10

    def test_get_users_with_count(self):
        """Проверяет GET /users с параметром count"""
        response = requests.get(f"{BASE_URL}/users?count=3")
        assert response.status_code == 200
        data = response.json()
        
        result = data["result"]
        assert len(result) == 3
        assert result[0]["id"] == 1
        assert result[-1]["id"] == 3

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
        
        result = data["result"]
        assert result == []  # Должен вернуть пустой список

    def test_get_users_invalid_offset(self):
        """Проверяет GET /users с некорректным offset"""
        response = requests.get(f"{BASE_URL}/users?offset=-5")
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=success_response_schema)
        assert data["result"] == []  # Должен вернуть пустой список

    def test_get_users_invalid_count(self):
        """Проверяет GET /users с некорректным count"""
        response = requests.get(f"{BASE_URL}/users?count=-3")
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=success_response_schema)
        assert data["result"] == []  # Должен вернуть пустой список

    def test_get_users_count_zero(self):
        """Проверяет специальное поведение: count=0 возвращает одного пользователя"""
        response = requests.get(f"{BASE_URL}/users?offset=3&count=0")
        assert response.status_code == 200
        data = response.json()
        
        result = data["result"]
        assert len(result) == 1
        assert result[0]["id"] == 4  # Пользователь с id=4 (offset=3)

    def test_get_users_invalid_params_type(self):
        """Проверяет GET /users с параметрами неверного типа"""
        response = requests.get(f"{BASE_URL}/users?offset=abc&count=def")
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=error_response_schema)
        assert "error" in data["status"]

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
        assert result["id"] == 11  # Следующий ID после 10
        
        # Проверяем, что пользователь действительно создан
        get_response = requests.get(f"{BASE_URL}/users/{result['id']}")
        assert get_response.status_code == 200
        user_data = get_response.json()
        assert user_data["result"]["name"] == "Test User"

    def test_create_user_without_name(self):
        """Проверяет создание пользователя без имени (name должен быть null)"""
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
        validate(instance=data, schema=error_response_schema)
        assert "Missing required field" in data["description"]

    def test_create_user_duplicate_msisdn(self):
        """Проверяет ошибку при создании с существующим msisdn"""
        new_user = {
            "name": "Test User",
            "msisdn": "79161234001"  # Уже существует в INITIAL_USERS
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=error_response_schema)
        assert "already exists" in data["description"]

    def test_create_user_name_too_long(self):
        """Проверяет ошибку при слишком длинном имени (больше 30 символов)"""
        new_user = {
            "name": "A" * 31,
            "msisdn": "79998887744"
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=error_response_schema)
        assert "must not exceed 30 characters" in data["description"]

    def test_create_user_invalid_msisdn_length(self):
        """Проверяет ошибку при неверной длине MSISDN"""
        # Слишком короткий
        response = requests.post(f"{BASE_URL}/users", json={
            "msisdn": "1234567890"  # 10 цифр
        })
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=error_response_schema)
        assert "exactly 11 digits" in data["description"]
        
        # Слишком длинный
        response = requests.post(f"{BASE_URL}/users", json={
            "msisdn": "123456789012"  # 12 цифр
        })
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=error_response_schema)
        assert "exactly 11 digits" in data["description"]

    def test_create_user_msisdn_with_letters(self):
        """Проверяет ошибку при MSISDN с буквами"""
        new_user = {
            "msisdn": "7916abc4567"
        }
        
        response = requests.post(f"{BASE_URL}/users", json=new_user)
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=error_response_schema)
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
        validate(instance=data, schema=error_response_schema)
        assert "Extra fields not allowed" in data["description"]

    def test_create_user_invalid_json(self):
        """Проверяет обработку невалидного JSON"""
        response = requests.post(
            f"{BASE_URL}/users", 
            data="not a json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=error_response_schema)

    # ===== ТЕСТЫ ДЛЯ GET /users/{id} =====
    
    def test_get_user_by_id(self):
        """Проверяет получение существующего пользователя по ID"""
        response = requests.get(f"{BASE_URL}/users/5")
        assert response.status_code == 200
        data = response.json()
        
        validate(instance=data, schema=success_response_schema)
        user = data["result"]
        validate(instance=user, schema=user_schema)
        assert user["id"] == 5
        assert user["name"] == "Clark Peterson"
        assert user["msisdn"] == "79161234005"

    def test_get_user_not_found(self):
        """Проверяет ошибку при запросе несуществующего пользователя"""
        response = requests.get(f"{BASE_URL}/users/999")
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=error_response_schema)
        assert "not found" in data["description"]

    def test_get_user_invalid_id_type(self):
        """Проверяет обработку некорректного типа ID"""
        response = requests.get(f"{BASE_URL}/users/abc")
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=error_response_schema)

    # ===== ТЕСТЫ ДЛЯ DELETE /users/{id} =====
    
    def test_delete_user(self):
        """Проверяет удаление существующего пользователя"""
        # Сначала создаем пользователя
        create_response = requests.post(f"{BASE_URL}/users", json={
            "msisdn": "79998887722"
        })
        user_id = create_response.json()["result"]["id"]
        
        # Удаляем его
        delete_response = requests.delete(f"{BASE_URL}/users/{user_id}")
        assert delete_response.status_code == 200
        data = delete_response.json()
        validate(instance=data, schema=success_response_schema)
        assert "deleted successfully" in data["result"]["message"]
        
        # Проверяем, что пользователь действительно удален
        get_response = requests.get(f"{BASE_URL}/users/{user_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "error"

    def test_delete_user_not_found(self):
        """Проверяет ошибку при удалении несуществующего пользователя"""
        response = requests.delete(f"{BASE_URL}/users/999")
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=error_response_schema)
        assert "not found" in data["description"]

    def test_delete_user_invalid_id(self):
        """Проверяет обработку некорректного ID при удалении"""
        response = requests.delete(f"{BASE_URL}/users/abc")
        assert response.status_code == 200
        data = response.json()
        validate(instance=data, schema=error_response_schema)

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

    def test_error_response_structure(self):
        """Проверяет структуру ответа с ошибкой"""
        response = requests.get(f"{BASE_URL}/users/999")
        data = response.json()
        
        assert "status" in data
        assert "description" in data
        assert data["status"] == "error"
        assert isinstance(data["description"], str)

    def test_success_response_structure(self):
        """Проверяет структуру успешного ответа"""
        response = requests.get(f"{BASE_URL}/users/1")
        data = response.json()
        
        assert "status" in data
        assert "result" in data
        assert data["status"] == "OK"

    # ===== ТЕСТЫ НА ВАЛИДАЦИЮ ДАННЫХ =====
    
    def test_user_data_validation(self):
        """Проверяет, что все пользователи соответствуют схеме"""
        response = requests.get(f"{BASE_URL}/users")
        users = response.json()["result"]
        
        for user in users:
            validate(instance=user, schema=user_schema)
            # Дополнительные проверки
            assert len(user["msisdn"]) == 11
            assert user["msisdn"].isdigit()
            if user["name"] is not None:
                assert len(user["name"]) <= 30

    def test_msisdn_uniqueness(self):
        """Проверяет уникальность MSISDN после создания"""
        # Получаем все MSISDN
        response = requests.get(f"{BASE_URL}/users")
        users = response.json()["result"]
        msisdns = [u["msisdn"] for u in users]
        
        # Проверяем уникальность
        assert len(msisdns) == len(set(msisdns))

    def test_id_auto_increment(self):
        """Проверяет автоинкремент ID"""
        # Получаем максимальный ID
        response = requests.get(f"{BASE_URL}/users")
        max_id = max(u["id"] for u in response.json()["result"])
        
        # Создаем пользователя
        create_response = requests.post(f"{BASE_URL}/users", json={
            "msisdn": "79998887700"
        })
        new_id = create_response.json()["result"]["id"]
        
        # Новый ID должен быть больше максимального
        assert new_id > max_id

    def test_pagination_consistency(self):
        """Проверяет согласованность пагинации"""
        # Получаем всех пользователей
        all_response = requests.get(f"{BASE_URL}/users")
        all_users = all_response.json()["result"]
        
        # Получаем постранично
        page1 = requests.get(f"{BASE_URL}/users?offset=0&count=3").json()["result"]
        page2 = requests.get(f"{BASE_URL}/users?offset=3&count=3").json()["result"]
        page3 = requests.get(f"{BASE_URL}/users?offset=6&count=3").json()["result"]
        
        # Объединяем страницы
        combined = page1 + page2 + page3
        
        # Сравниваем с полным списком (первые 9 пользователей)
        assert combined == all_users[:9]

# ===== ФИКСТУРЫ И ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

@pytest.fixture(scope="session")
def api_available():
    """Проверяет доступность API перед запуском тестов"""
    try:
        response = requests.get(f"{BASE_URL}/users", timeout=5)
        return response.status_code == 200
    except:
        return False

def pytest_configure(config):
    """Вывод информации о запуске тестов"""
    print(f"\n🚀 Запуск тестов для QATest API")
    print(f"📡 Базовый URL: {BASE_URL}")
    print(f"📋 Всего тестов: {len([name for name in dir(TestQATestAPI) if name.startswith('test_')])}")
    print("-" * 50)

if __name__ == "__main__":
    pytest.main(["-v", "--tb=short", __file__])
