import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi_pagination import Page, add_pagination
from fastapi_pagination.ext.sqlalchemy import paginate as sqlalchemy_pagination
from fastapi_filter.contrib.sqlalchemy import Filter
from passlib.context import CryptContext
from sqlalchemy.orm import selectinload, joinedload
from jose import jwt, JWTError
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, declarative_base, sessionmaker, relationship
from sqlalchemy import create_engine, Column, String, Integer, ForeignKey, DateTime, Text, Table
from typing import Optional, List

SECRET_KEY = os.getenv("SECRET_KEY", "my_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 10

DATABASE_URL = "sqlite:///database.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
app = FastAPI()
add_pagination(app)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def password_hash(password):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


enrollments = Table(
    "enrollments",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("course_id", Integer, ForeignKey("courses.id"), primary_key=True)
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, default="student")  # "student" или "teacher"

    taught_courses = relationship("Course", back_populates="teacher")
    enrolled_courses = relationship("Course", secondary=enrollments, back_populates="students")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), index=True)

    teacher = relationship("User", back_populates="taught_courses")
    students = relationship("User", secondary=enrollments, back_populates="enrolled_courses")
    assignments = relationship("Assignment", back_populates="course")


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), index=True)

    course = relationship("Course", back_populates="assignments")


class RefreshTokenDB(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    user_role = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

    user = relationship("User")


def create_access_token(username: str, role: str):
    payload = {'sub': username, 'role': role, 'exp': datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(username: str, role: str):
    payload = {'sub': username, 'role': role, 'type': 'refresh',
               'exp': datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def save_refresh_token(db: Session, user: User, refresh_token: str):
    refresh = RefreshTokenDB(user_id=user.id, token=refresh_token, user_role=user.role, created_at=datetime.utcnow(),
                             expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    db.add(refresh)
    db.commit()
    db.refresh(refresh)
    return refresh


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token is invalid")


class CreateUser(BaseModel):
    username: str
    password: str
    email: str
    role: str = "student"


class Token(BaseModel):
    access_token: str
    token_type: str = "Bearer"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class CreateCourse(BaseModel):
    title: str
    description: Optional[str] = None
    teacher_id: int


class CreateAssignment(BaseModel):
    title: str
    description: Optional[str] = None
    course_id: int


class CreateRefreshTokenDB(BaseModel):
    user_id: int
    token: str
    user_role: str
    expires_at: datetime


class UserSimpleOutput(BaseModel):
    id: int
    username: str
    email: str
    role: str

    class Config:
        from_attributes = True


class CourseSimpleOutput(BaseModel):
    id: int
    title: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class AssignmentSimpleOutput(BaseModel):
    id: int
    title: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class AssignmentOutput(BaseModel):
    id: int
    title: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class CourseOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    students: List[UserSimpleOutput] = Field(default_factory=list)
    assignments: List[AssignmentSimpleOutput] = Field(default_factory=list)

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    taught_courses: List[CourseSimpleOutput] = Field(default_factory=list)
    enrolled_courses: List[CourseSimpleOutput] = Field(default_factory=list)

    class Config:
        from_attributes = True


class UpdateUser(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None

    class Config:
        from_attributes = True


class UpdateCourse(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class UpdateAssignment(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, username: str, email: str, password: str):
        if self.db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="Username already in use.")
        if self.db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=400, detail="Email already in use.")
        hashed_password = password_hash(password)
        new_user = User(username=username, email=email, hashed_password=hashed_password, role="student")
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        return new_user

    def login_user(self, username: str, password: str):
        user = self.db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Incorrect password.")
        return user


class UserFilter(Filter):
    username__ilike: Optional[str] = None
    email__ilike: Optional[str] = None
    taught_courses__title__ilike: Optional[str] = None

    class Constants(Filter.Constants):
        model = User


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_filtered_users(self, filters: UserFilter):
        query = self.db.query(User).options(selectinload(User.taught_courses), selectinload(User.enrolled_courses))
        return filters.filter(query)

    def get_filtered_user_id(self, user_id: int):
        return self.db.query(User).filter(User.id == user_id).first()

    def update_user(self, user_id: int, data: UpdateUser):
        obj = self.db.query(User).filter(User.id == user_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="User not found.")
        if data.username is not None:
            obj.username = data.username
        if data.email is not None:
            obj.email = data.email
        if data.password is not None:
            obj.hashed_password = password_hash(data.password)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete_user(self, user_id: int):
        obj = self.db.query(User).filter(User.id == user_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="User not found.")
        self.db.delete(obj)
        self.db.commit()
        return obj


class CourseFilter(Filter):
    title__ilike: Optional[str] = None
    teacher_id__eq: Optional[int] = None
    students__username__ilike: Optional[str] = None
    assignments__title__ilike: Optional[str] = None

    class Constants(Filter.Constants):
        model = Course


class CourseService:
    def __init__(self, db: Session):
        self.db = db

    def get_filtered_courses(self, filters: CourseFilter):
        query = self.db.query(Course).options(selectinload(Course.students), selectinload(Course.assignments),
                                              joinedload(Course.teacher))
        return filters.filter(query)

    def get_filtered_course_id(self, user_id: int):
        return self.db.query(Course).filter(Course.id == user_id).first()

    def create_course(self, data: CreateCourse):
        if self.db.query(Course).filter(Course.title == data.title, Course.teacher_id == data.teacher_id).first():
            raise HTTPException(status_code=400, detail="Course already exists.")
        new_course = Course(title=data.title, teacher_id=data.teacher_id, description=data.description)
        self.db.add(new_course)
        self.db.commit()
        self.db.refresh(new_course)
        return new_course

    def update_course(self, course_id: int, data: UpdateCourse):
        obj = self.db.query(Course).filter(Course.id == course_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="Course not found.")
        if data.title is not None:
            obj.title = data.title
        if data.description is not None:
            obj.description = data.description
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete_course(self, course_id: int):
        obj = self.db.query(Course).filter(Course.id == course_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="Course not found.")
        self.db.delete(obj)
        self.db.commit()
        return obj


class AssignmentFilter(Filter):
    title__ilike: Optional[str] = None
    course_id__eq: Optional[int] = None

    class Constants(Filter.Constants):
        model = Assignment


class AssignmentService:
    def __init__(self, db: Session):
        self.db = db

    def get_filtered_assignments(self, filters: AssignmentFilter):
        query = self.db.query(Assignment).options(joinedload(Assignment.course))
        return filters.filter(query)

    def get_filtered_assignment_id(self, assignment_id: int):
        return self.db.query(Assignment).filter(Assignment.id == assignment_id).first()

    def update_assignment(self, assignment_id: int, data: UpdateAssignment):
        obj = self.db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="Assignment not found.")
        if data.title is not None:
            obj.title = data.title
        if data.description is not None:
            obj.description = data.description
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete_assignment(self, assignment_id: int):
        obj = self.db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="Assignment not found.")
        self.db.delete(obj)
        self.db.commit()
        return obj


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=400, detail="Invalid token.")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You are not an admin.")
    return current_user


Base.metadata.create_all(bind=engine)


@app.post('/users/register', response_model=UserOut)
def register(user: CreateUser, db: Session = Depends(get_db)):
    auth = AuthService(db)
    user = auth.register_user(user.username, user.email, user.password)
    return user


@app.post('/users/login', response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    auth = AuthService(db)
    user = auth.login_user(form_data.username, form_data.password)
    access_token = create_access_token(username=user.username, role=user.role)
    refresh_token = create_refresh_token(username=user.username)
    save_refresh_token(db, user, refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer"
    }


@app.post('/users/refresh', response_model=TokenResponse)
def refresh(data: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(data.refresh_token, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=400, detail="Invalid token.")
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid token.")
    db_token = db.query(RefreshTokenDB).filter_by(token=data.refresh_token).first()
    if not db_token:
        raise HTTPException(status_code=404, detail="Token not found.")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    access_token = create_access_token(username=user.username, role=user.role)
    refresh_token = create_refresh_token(username=user.username)
    save_refresh_token(db, user, refresh_token)
    db.delete(db_token)
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer"
    }


@app.get('/users/me', response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.get('/users', response_model=Page[UserOut])
def read_users(db: Session = Depends(get_db), filters: UserFilter = Depends(), _: User = Depends(require_admin)):
    service = UserService(db)
    user = service.get_filtered_users(filters)
    return sqlalchemy_pagination(user)


@app.get('/users/{user_id}', response_model=UserOut)
def read_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    service = UserService(db)
    user = service.get_filtered_user_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@app.put('/users/{user_id}', response_model=UserOut)
def update_user(user_id: int, user_update: UpdateUser, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    service = UserService(db)
    user = service.update_user(user_id, user_update)
    return user


@app.delete('/users/{user_id}', response_model=UserOut)
def delete_users(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    service = UserService(db)
    user = service.delete_user(user_id)
    return user


@app.post('/courses', response_model=CourseOut)
def create_course(course: CreateCourse, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    check_teacher = db.query(User).filter(User.id == course.teacher_id).first()
    if not check_teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    service = CourseService(db)
    new_course = service.create_course(course)
    return new_course


@app.get('/courses', response_model=Page[CourseOut])
def read_courses(db: Session = Depends(get_db), filters: CourseFilter = Depends()):
    service = CourseService(db)
    course = service.get_filtered_courses(filters)
    return sqlalchemy_pagination(course)


@app.get('/courses/{course_id}', response_model=CourseOut)
def read_course(course_id: int, db: Session = Depends(get_db)):
    service = CourseService(db)
    course = service.get_filtered_course_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    return course


@app.put('/courses/{course_id}', response_model=CourseOut)
def update_course(course_id: int, course_update: UpdateCourse, db: Session = Depends(get_db),
                  _: User = Depends(require_admin)):
    service = CourseService(db)
    course = service.update_course(course_id, course_update)
    return course


@app.delete('/courses/{course_id}', response_model=CourseOut)
def delete_courses(course_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    service = CourseService(db)
    course = service.delete_course(course_id)
    return course


@app.post('/courses/{course_id}/enroll', response_model=UserOut)
def add_user_to_course(course_id: int, user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    course = db.query(Course).filter(Course.id == course_id).first()
    user = db.query(User).filter(User.id == user_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user in course.students:
        raise HTTPException(status_code=401, detail="User is already enrolled.")
    course.students.append(user)
    db.commit()
    db.refresh(course)
    return user


@app.delete('/courses/{course_id}/enroll', response_model=UserOut)
def delete_user_from_course(course_id: int, user_id: int, db: Session = Depends(get_db),
                            _: User = Depends(require_admin)):
    course = db.query(Course).filter(Course.id == course_id).first()
    user = db.query(User).filter(User.id == user_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user not in course.students:
        raise HTTPException(status_code=401, detail="User not found")
    course.students.remove(user)
    db.commit()
    db.refresh(course)
    return user
