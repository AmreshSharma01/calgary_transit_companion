from database.db_setup import Base, engine
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)