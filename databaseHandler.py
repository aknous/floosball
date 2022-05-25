import os
import mysql.connector as database

_username = 'aknous'
_password = 'die4Waep!!'
_host = '192.168.1.41'
_database = 'floosball'

_divisionName = "Copper"
_standings = "WASHINGTON BELTS - 13 - 6, ... "

connection = database.connect(
    user = _username,
    password = _password,
    host = _host,
    database = _database
)

cursor = connection.cursor()

def add_data(divisionName, standings):
    try:
        statement = "INSERT INTO division (name, standings) VALUES (%s, %s)"
        data = (divisionName, standings)
        cursor.execute(statement, data)
        connection.commit()
        print("Successfully added entry to database")
    except database.Error as e:
        print(f"Error adding entry to database: {e}")

def get_data(divisionName):
    try:
        statement = "SELECT name, standings FROM division WHERE name=%s"
        data = (divisionName,)
        cursor.execute(statement, data)
        for x, y in cursor:
            print(f"Successfully retrieved {x}, {y}")
    except database.Error as e:
        print(f"Error retrieving entry from database: {e}")

add_data(_divisionName, _standings)
get_data(_divisionName)

connection.close()
