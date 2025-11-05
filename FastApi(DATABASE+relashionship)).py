from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session, declarative_base, sessionmaker, relationship
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from typing import List

DATABASE_URL = "sqlite:///database.db"
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()


class Author(Base):
    __tablename__ = "authors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String)
    books = relationship("Book", back_populates="author")


class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    author_id = Column(Integer, ForeignKey("authors.id"))
    author = relationship("Author", back_populates="books")
    chapters = relationship("Chapter", back_populates="book")


class Chapter(Base):
    __tablename__ = "chapters"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    content = Column(String)
    book_id = Column(Integer, ForeignKey("books.id"))
    book = relationship("Book", back_populates="chapters")


class CreateAuthor(BaseModel):
    name: str
    email: str


class CreateBook(BaseModel):
    title: str
    description: str
    author_id: int


class CreateChapter(BaseModel):
    title: str
    content: str
    book_id: int


class ChapterOut(BaseModel):
    id: int
    title: str
    content: str
    book_id: int

    class Config:
        orm_mode = True


class BookOut(BaseModel):
    id: int
    title: str
    description: str
    author_id: int

    class Config:
        orm_mode = True


class AuthorOut(BaseModel):
    id: int
    name: str
    email: str
    books: List[BookOut] = []

    class Config:
        orm_mode = True


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(bind=engine)


@app.post("/authors", response_model=AuthorOut)
def create_authors(author: CreateAuthor, db: Session = Depends(get_db)):
    if db.query(Author).filter(Author.email == author.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    new_author = Author(name=author.name, email=author.email)
    db.add(new_author)
    db.commit()
    db.refresh(new_author)
    return new_author


@app.get("/authors", response_model=List[AuthorOut])
def read_authors(db: Session = Depends(get_db)):
    return db.query(Author).all()


@app.get("/authors/{author_id}", response_model=AuthorOut)
def read_author(author_id: int, db: Session = Depends(get_db)):
    get_author = db.query(Author).filter(Author.id == author_id).first()
    if not get_author:
        raise HTTPException(status_code=404, detail="Author not found")
    return get_author


@app.put("/authors/{author_id}", response_model=AuthorOut)
def update_author(author_id: int, author: CreateAuthor, db: Session = Depends(get_db)):
    put_author = db.query(Author).filter(Author.id == author_id).first()
    if not put_author:
        raise HTTPException(status_code=404, detail="Author not found")
    if db.query(Author).filter(Author.name == author.name, Author.email == author.email,
                               Author.id != author_id).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    put_author.name = author.name
    put_author.email = author.email
    db.commit()
    db.refresh(put_author)
    return put_author


@app.delete("/authors/{author_id}")
def delete_authors(author_id: int, db: Session = Depends(get_db)):
    delete_author = db.query(Author).filter(Author.id == author_id).first()
    if not delete_author:
        raise HTTPException(status_code=404, detail="Author not found")
    db.delete(delete_author)
    db.commit()
    return {'message': 'Author deleted'}


@app.post("/books", response_model=BookOut)
def create_book(book: CreateBook, db: Session = Depends(get_db)):
    check_author = db.query(Author).filter(Author.id == book.author_id).first()
    if not check_author:
        raise HTTPException(status_code=404, detail="Author not found")
    if db.query(Book).filter(Book.title == book.title).first():
        raise HTTPException(status_code=400, detail="Title already registered")
    new_book = Book(title=book.title, description=book.description, author_id=book.author_id)
    db.add(new_book)
    db.commit()
    db.refresh(new_book)
    return new_book


@app.get("/books", response_model=List[BookOut])
def read_books(db: Session = Depends(get_db)):
    return db.query(Book).all()


@app.get("/books/{book_id}", response_model=BookOut)
def read_book(book_id: int, db: Session = Depends(get_db)):
    get_book = db.query(Book).filter(Book.id == book_id).first()
    if not get_book:
        raise HTTPException(status_code=404, detail="Book not found")
    return get_book


@app.put("/books/{book_id}", response_model=BookOut)
def update_book(book_id: int, book: CreateBook, db: Session = Depends(get_db)):
    put_book = db.query(Book).filter(Book.id == book_id).first()
    if not put_book:
        raise HTTPException(status_code=404, detail="Book not found")
    if db.query(Book).filter(Book.title == book.title, Book.description == book.description,
                             Book.id != book_id).first():
        raise HTTPException(status_code=400, detail="Title already registered")
    put_book.title = book.title
    put_book.description = book.description
    put_book.author_id = book.author_id
    db.commit()
    db.refresh(put_book)
    return put_book


@app.delete("/books/{book_id}")
def delete_books(book_id: int, db: Session = Depends(get_db)):
    delete_book = db.query(Book).filter(Book.id == book_id).first()
    if not delete_book:
        raise HTTPException(status_code=404, detail="Book not found")
    db.delete(delete_book)
    db.commit()
    return {'message': 'Book deleted'}


@app.post("/chapters", response_model=ChapterOut)
def create_chapters(chapter: CreateChapter, db: Session = Depends(get_db)):
    check_book = db.query(Book).filter(Book.id == chapter.book_id).first()
    if not check_book:
        raise HTTPException(status_code=404, detail="Book not found")
    if db.query(Chapter).filter(Chapter.title == chapter.title).first():
        raise HTTPException(status_code=400, detail="Title already registered")
    new_chapter = Chapter(title=chapter.title, content=chapter.content, book_id=chapter.book_id)
    db.add(new_chapter)
    db.commit()
    db.refresh(new_chapter)
    return new_chapter


@app.get("/chapters", response_model=List[ChapterOut])
def read_chapters(db: Session = Depends(get_db)):
    return db.query(Chapter).all()


@app.get("/chapters/{chapter_id}", response_model=ChapterOut)
def read_chapter(chapter_id: int, db: Session = Depends(get_db)):
    get_chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not get_chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return get_chapter


@app.put("/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(chapter_id: int, chapter: CreateChapter, db: Session = Depends(get_db)):
    put_chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not put_chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    if db.query(Chapter).filter(Chapter.content == chapter.content, Chapter.title == chapter.title,
                                Chapter.id != chapter_id).first():
        raise HTTPException(status_code=400, detail="Title already registered")
    put_chapter.content = chapter.content
    put_chapter.title = chapter.title
    put_chapter.book_id = chapter.book_id
    db.commit()
    db.refresh(put_chapter)
    return put_chapter


@app.delete("/chapters/{chapter_id}")
def delete_chapters(chapter_id: int, db: Session = Depends(get_db)):
    delete_chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not delete_chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    db.delete(delete_chapter)
    db.commit()
    return {'message': 'Chapter deleted'}
