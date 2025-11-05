from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session, declarative_base, sessionmaker, relationship
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from pydantic import BaseModel
from typing import List

DATABASE_URL = "sqlite:///database.db"
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
app = FastAPI()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String)
    orders = relationship("Order", backref="user", cascade="all, delete")


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    price = Column(Float)
    orders = relationship("Order", back_populates="product", cascade="all, delete")


class CreateUser(BaseModel):
    name: str
    email: str


class CreateOrder(BaseModel):
    user_id: int
    product_id: int
    quantity: int


class CreateProduct(BaseModel):
    name: str
    price: float


class OrderOut(BaseModel):
    id: int
    user_id: int
    product_id: int
    quantity: int

    class Config:
        orm_mode = True


class ProductOut(BaseModel):
    id: int
    name: str
    price: float

    class Config:
        orm_mode = True


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    orders: List[OrderOut] = []

    class Config:
        orm_mode = True


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(engine)


@app.get("/users", response_model=List[UserOut])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@app.get("/users/{user_id}", response_model=UserOut)
def get_users(user_id: int, db: Session = Depends(get_db)):
    get_user1 = db.query(User).filter(User.id == user_id).first()
    if not get_user1:
        raise HTTPException(status_code=404, detail="User not found")
    return get_user1


@app.post("/users", response_model=UserOut)
def create_user(user: CreateUser, db: Session = Depends(get_db)):
    if db.query(User).filter(User.name == user.name).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    new_user = User(name=user.name, email=user.email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, user: CreateUser, db: Session = Depends(get_db)):
    put_user = db.query(User).filter(User.id == user_id).first()
    if not put_user:
        raise HTTPException(status_code=404, detail="User not found")
    if db.query(User).filter(User.name == user.name, User.id != user_id).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    if db.query(User).filter(User.email == user.email, User.id != user_id).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    put_user.name = user.name
    put_user.email = user.email
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
    return {'message': 'User deleted'}


@app.get("/products", response_model=List[ProductOut])
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()


@app.get("/products/{product_id}", response_model=ProductOut)
def get_products(product_id: int, db: Session = Depends(get_db)):
    get_product = db.query(Product).filter(Product.id == product_id).first()
    if not get_product:
        raise HTTPException(status_code=404, detail="Product not found")
    return get_product


@app.post("/products", response_model=ProductOut)
def create_product(product: CreateProduct, db: Session = Depends(get_db)):
    if db.query(Product).filter(Product.name == product.name).first():
        raise HTTPException(status_code=400, detail="Product name already exists")
    new_product = Product(name=product.name, price=product.price)
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@app.put("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: int, product: CreateProduct, db: Session = Depends(get_db)):
    put_product = db.query(Product).filter(Product.id == product_id).first()
    if not put_product:
        raise HTTPException(status_code=404, detail="Product not found")
    if db.query(Product).filter(Product.name == product.name, Product.id != product_id).first():
        raise HTTPException(status_code=400, detail="Product name already exists")
    put_product.name = product.name
    put_product.price = product.price
    db.commit()
    db.refresh(put_product)
    return put_product


@app.delete("/products/{product_id}")
def delete_products(product_id: int, db: Session = Depends(get_db)):
    delete_product = db.query(Product).filter(Product.id == product_id).first()
    if not delete_product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(delete_product)
    db.commit()
    return {'message': 'Product deleted'}


@app.get("/orders", response_model=List[OrderOut])
def get_orders(db: Session = Depends(get_db)):
    return db.query(Order).all()


@app.get("/orders/{order_id}", response_model=OrderOut)
def get_orders(order_id: int, db: Session = Depends(get_db)):
    get_order = db.query(Order).filter(Order.id == order_id).first()
    if not get_order:
        raise HTTPException(status_code=404, detail="Order not found")
    return get_order


@app.post("/orders", response_model=OrderOut)
def create_order(order: CreateOrder, db: Session = Depends(get_db)):
    check_user = db.query(User).filter(User.id == order.user_id).first()
    if not check_user:
        raise HTTPException(status_code=404, detail="User not found")
    check_product = db.query(Product).filter(Product.id == order.product_id).first()
    if not check_product:
        raise HTTPException(status_code=404, detail="Product not found")
    new_order = Order(user_id=order.user_id, product_id=order.product_id, quantity=order.quantity)
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order


@app.put("/orders/{order_id}", response_model=OrderOut)
def update_order(order_id: int, order: CreateOrder, db: Session = Depends(get_db)):
    put_order = db.query(Order).filter(Order.id == order_id).first()
    if not put_order:
        raise HTTPException(status_code=404, detail="Order not found")
    check_user = db.query(User).filter(User.id == order.user_id).first()
    if not check_user:
        raise HTTPException(status_code=404, detail="User not found")
    check_product = db.query(Product).filter(Product.id == order.product_id).first()
    if not check_product:
        raise HTTPException(status_code=404, detail="Product not found")
    if db.query(Order).filter(Order.user_id == order.user_id,
                              Order.product_id == order.product_id,
                              Order.id != order_id).first():
        raise HTTPException(status_code=400, detail="Order already exists")
    put_order.user_id = order.user_id
    put_order.product_id = order.product_id
    put_order.quantity = order.quantity
    db.commit()
    db.refresh(put_order)
    return put_order


@app.delete("/orders/{order_id}")
def delete_orders(order_id: int, db: Session = Depends(get_db)):
    delete_order = db.query(Order).filter(Order.id == order_id).first()
    if not delete_order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(delete_order)
    db.commit()
    return {'message': 'Order deleted'}
