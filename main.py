from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session, declarative_base, sessionmaker, relationship
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean
from typing import List

DATABASE_URL = "sqlite:///database.db"
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    email = Column(String)
    is_active = Column(Boolean)
    posts = relationship("Post", back_populates="user", cascade="all, delete")


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    content = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="posts")


class CreateUser(BaseModel):
    username: str
    email: str
    is_active: bool = True


class CreatePost(BaseModel):
    title: str
    content: str
    user_id: int


class PostOut(BaseModel):
    id: int
    title: str
    content: str
    user_id: int

    class Config:
        orm_mode = True


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool = True
    posts: List[PostOut] = []

    class Config:
        orm_mode = True


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(bind=engine)


@app.get("/users", response_model=List[UserOut])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    new_user = db.query(User).filter(User.id == user_id).first()
    if not new_user:
        raise HTTPException(status_code=404, detail="User not found")
    return new_user


@app.post("/users", response_model=UserOut)
def create_user(user: CreateUser, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    new_user1 = User(username=user.username, email=user.email, is_active=user.is_active)
    db.add(new_user1)
    db.commit()
    db.refresh(new_user1)
    return new_user1


@app.put("/users/{user_id}")
def update_user(user_id: int, user: CreateUser, db: Session = Depends(get_db)):
    put_user = db.query(User).filter(User.id == user_id).first()
    if not put_user:
        raise HTTPException(status_code=404, detail="User not found")
    put_user.username = user.username
    put_user.email = user.email
    put_user.is_active = user.is_active
    db.commit()
    db.refresh(put_user)
    return put_user


@app.delete("/users/{user_id}")
def delete_users(user_id: int, db: Session = Depends(get_db)):
    delete_user = db.query(User).filter(User.id == user_id).first()
    if not delete_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(delete_user)
    db.commit()
    return delete_user


@app.get("/posts", response_model=List[PostOut])
def get_posts(db: Session = Depends(get_db)):
    return db.query(Post).all()


@app.get("/posts/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Session = Depends(get_db)):
    get_post1 = db.query(Post).filter(Post.id == post_id).first()
    if not get_post1:
        raise HTTPException(status_code=404, detail="Post not found")
    return get_post1


@app.post("/users/{user_id}/posts", response_model=PostOut)
def create_post(user_id: int, post: CreatePost, db: Session = Depends(get_db)):
    check_user = db.query(User).filter(User.id == user_id).first()
    if not check_user:
        raise HTTPException(status_code=404, detail="User not found")
    new_post = Post(title=post.title, content=post.content, user_id=user_id)
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


@app.put("/posts/{post_id}")
def upgrade_post(post: CreatePost, post_id: int, db: Session = Depends(get_db)):
    put_post = db.query(Post).filter(Post.id == post_id).first()
    if not put_post:
        raise HTTPException(status_code=404, detail="Post not found")
    put_post.title = post.title
    put_post.content = post.content
    put_post.user_id = post.user_id
    db.commit()
    db.refresh(put_post)
    return put_post


@app.delete("/posts/{post_id}")
def delete_posts(post_id: int, db: Session = Depends(get_db)):
    delete_post = db.query(Post).filter(Post.id == post_id).first()
    if not delete_post:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(delete_post)
    db.commit()
    return {'message': 'Post deleted'}
