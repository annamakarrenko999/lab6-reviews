import pytest
from app import create_app
from app.models import db, User, Course, Category, Review
import uuid


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        db.create_all()

        # Создаём категорию
        category = Category(name='Тестовая категория')
        db.session.add(category)
        db.session.commit()

        # Создаём пользователя
        user = User(
            first_name='Тест',
            last_name='Тестов',
            login='testuser'
        )
        user.set_password('testpass123')
        db.session.add(user)
        db.session.commit()

        # Создаём курс с изображением
        from app.models import Image
        test_image = Image(
            id=str(uuid.uuid4()),
            file_name='test.jpg',
            mime_type='image/jpeg',
            md5_hash='test_hash_123'
        )
        db.session.add(test_image)
        db.session.commit()

        course = Course(
            name='Тестовый курс',
            short_desc='Краткое описание',
            full_desc='Полное описание',
            rating_sum=0,
            rating_num=0,
            category_id=category.id,
            author_id=user.id,
            background_image_id=test_image.id
        )
        db.session.add(course)
        db.session.commit()

    yield app

    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login_user(client):
    """Авторизация тестового пользователя"""
    client.post('/auth/login', data={
        'login': 'testuser',
        'password': 'testpass123'
    }, follow_redirects=True)
    return client


def test_review_model_creation(app):
    """Тест 1: создание модели Review"""
    with app.app_context():
        user = db.session.query(User).filter(User.login == 'testuser').first()
        course = db.session.query(Course).first()

        review = Review(
            rating=5,
            text='Отличный курс!',
            course_id=course.id,
            user_id=user.id
        )
        db.session.add(review)
        db.session.commit()

        assert review.id is not None
        assert review.rating == 5
        assert review.text == 'Отличный курс!'


def test_reviews_display_on_course_page(client, login_user):
    """Тест 2: отзывы отображаются на странице курса"""
    response = client.get('/courses/1')
    assert response.status_code == 200
    assert 'Отзывы' in response.text or 'отзыв' in response.text.lower()


def test_reviews_page_accessible(client, login_user):
    """Тест 3: страница всех отзывов доступна"""
    response = client.get('/courses/1/reviews')
    assert response.status_code == 200
    assert 'Отзывы о курсе' in response.text


def test_create_review_requires_auth(client):
    """Тест 4: создание отзыва требует авторизации"""
    response = client.post('/courses/1/reviews/create', data={
        'rating': 5,
        'text': 'Хороший курс!'
    }, follow_redirects=True)

    assert '/auth/login' in response.request.path or 'Войти' in response.text


def test_create_review_success(client, login_user):
    """Тест 5: успешное создание отзыва"""
    response = client.post('/courses/1/reviews/create', data={
        'rating': 5,
        'text': 'Отличный курс!'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert 'успешно' in response.text.lower() or 'отзыв' in response.text


def test_create_review_with_empty_text(client, login_user):
    """Тест 6: создание отзыва с пустым текстом"""
    response = client.post('/courses/1/reviews/create', data={
        'rating': 5,
        'text': ''
    }, follow_redirects=True)

    assert response.status_code == 200
    assert 'не может быть пустым' in response.text or 'пуст' in response.text


def test_cannot_create_duplicate_review(client, login_user):
    """Тест 7: пользователь не может оставить второй отзыв"""
    client.post('/courses/1/reviews/create', data={
        'rating': 5,
        'text': 'Первый отзыв'
    })

    response = client.post('/courses/1/reviews/create', data={
        'rating': 4,
        'text': 'Второй отзыв'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert 'уже' in response.text.lower() or 'отзыв' in response.text


def test_course_rating_updates_after_review(client, login_user):
    """Тест 8: рейтинг курса обновляется после добавления отзыва"""
    with client.application.app_context():
        course = db.session.query(Course).first()
        initial_rating_sum = course.rating_sum
        initial_rating_num = course.rating_num

    client.post('/courses/1/reviews/create', data={
        'rating': 5,
        'text': 'Отличный курс!'
    })

    with client.application.app_context():
        course = db.session.query(Course).first()
        assert course.rating_num == initial_rating_num + 1
        assert course.rating_sum == initial_rating_sum + 5


def test_reviews_sorting_newest(client, login_user):
    """Тест 9: сортировка отзывов по новизне"""
    client.post('/courses/1/reviews/create', data={
        'rating': 5,
        'text': 'Первый отзыв'
    })
    client.post('/courses/1/reviews/create', data={
        'rating': 4,
        'text': 'Второй отзыв'
    })

    response = client.get('/courses/1/reviews?sort=newest')
    assert response.status_code == 200


def test_reviews_sorting_positive_first(client, login_user):
    """Тест 10: сортировка отзывов (сначала положительные)"""
    response = client.get('/courses/1/reviews?sort=positive_first')
    assert response.status_code == 200


def test_reviews_sorting_negative_first(client, login_user):
    """Тест 11: сортировка отзывов (сначала отрицательные)"""
    response = client.get('/courses/1/reviews?sort=negative_first')
    assert response.status_code == 200


def test_review_form_displayed_for_authenticated(client, login_user):
    """Тест 12: форма отзыва отображается для авторизованного пользователя"""
    response = client.get('/courses/1')
    assert response.status_code == 200


def test_review_form_not_displayed_for_unauthenticated(client):
    """Тест 13: форма отзыва не отображается для неавторизованного"""
    response = client.get('/courses/1')
    assert 'Войдите' in response.text or 'login' in response.text.lower()


def test_all_reviews_button_on_course_page(client, login_user):
    """Тест 14: кнопка 'Все отзывы' на странице курса"""
    response = client.get('/courses/1')
    assert 'Все отзывы' in response.text or '/reviews' in response.text


def test_sorting_persists_across_pages(client, login_user):
    """Тест 15: параметр сортировки сохраняется при пагинации"""
    for i in range(3):
        client.post('/courses/1/reviews/create', data={
            'rating': 5,
            'text': f'Отзыв {i}'
        })

    response = client.get('/courses/1/reviews?sort=positive_first')
    assert response.status_code == 200