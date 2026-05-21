from app.models import Review, db
from sqlalchemy import desc, asc


class ReviewRepository:
    def __init__(self, db):
        self.db = db

    def get_reviews_by_course(self, course_id, sort='newest', page=1, per_page=10):
        """Получение отзывов курса с пагинацией и сортировкой"""
        query = self.db.select(Review).where(Review.course_id == course_id)

        if sort == 'newest':
            query = query.order_by(desc(Review.created_at))
        elif sort == 'positive_first':
            query = query.order_by(desc(Review.rating), desc(Review.created_at))
        elif sort == 'negative_first':
            query = query.order_by(asc(Review.rating), desc(Review.created_at))

        pagination = self.db.paginate(query, page=page, per_page=per_page)
        return pagination

    def get_recent_reviews(self, course_id, limit=5):
        """Получение последних 5 отзывов"""
        query = self.db.select(Review)\
            .where(Review.course_id == course_id)\
            .order_by(desc(Review.created_at))\
            .limit(limit)
        return self.db.session.execute(query).scalars().all()

    def get_user_review_for_course(self, user_id, course_id):
        """Получение отзыва пользователя на курс (если есть)"""
        query = self.db.select(Review).where(
            Review.user_id == user_id,
            Review.course_id == course_id
        )
        return self.db.session.execute(query).scalar()

    def add_review(self, user_id, course_id, rating, text):
        """Добавление нового отзыва"""
        review = Review(
            user_id=user_id,
            course_id=course_id,
            rating=rating,
            text=text
        )
        self.db.session.add(review)
        self.db.session.commit()
        return review

    def update_course_rating(self, course_id):
        """Пересчёт рейтинга курса"""
        from app.models import Course
        course = self.db.session.get(Course, course_id)
        if course:
            reviews = self.get_reviews_by_course(course_id, per_page=1000).items
            if reviews:
                total_rating = sum(r.rating for r in reviews)
                course.rating_sum = total_rating
                course.rating_num = len(reviews)
            else:
                course.rating_sum = 0
                course.rating_num = 0
            self.db.session.commit()