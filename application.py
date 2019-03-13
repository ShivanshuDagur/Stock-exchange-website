import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    #extracting all the stocks and number of shares of each stock owned by loginned user from the prortfolio table
    # will have list of dictionary in format[{'SUM(number_of_shares)':20, 'symbol':GOOG},{...},...]
    shares = db.execute("SELECT SUM(number_of_shares),symbol FROM portfolio WHERE id =:userid GROUP BY symbol ",
                        userid=session["user_id"])

    #a list to store all the content of a single row,which is later appended in list of list which represents the whole table
    listt = []

    #list containing all the rows of table in index page
    listoflist = []

    #grand total of the last column
    amount = 0

    for i in shares:
        #making sure stock whith 0 shares doesn't go into the index page table
        if i["SUM(number_of_shares)"] > 0:
            value = lookup(i["symbol"])

            #storing values in a row actually list
            listt.append(value["symbol"])
            listt.append(value["name"])
            listt.append(i["SUM(number_of_shares)"])
            listt.append(usd(value["price"]))
            listt.append(usd(value["price"] * i["SUM(number_of_shares)"]))

            #appending every row to the table actually listoflist
            listoflist.append(listt)
            #empty the list to store the other rows
            listt = []

            amount = amount + value["price"] * i["SUM(number_of_shares)"]

    cash = db.execute("SELECT cash from users WHERE ID =:userid",userid=session["user_id"])
    amount = amount + cash[0]['cash']

    return render_template("index.html", shares=listoflist, money=usd(cash[0]['cash']), grandtotal=usd(amount))



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        value = lookup(request.form.get("symbol"))


        if value == None:
            return apology("Must give correct symbol")
        #finding cash held by the user in users table
        wallet1 = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
        wallet = wallet1[0]["cash"]

        #checking if users has entered string value, fractinal or -ve value in number of shares field
        if request.form.get('shares').isalpha():
            return apology("Give numeric value")

        elif '.' in request.form.get("shares"):
            return apology('Give positive integer value')

        elif (int(request.form.get("shares"))) < 0:
            return apology('Give positive integer value')

        #calculating the amount to be spent on purchase
        amount = value["price"] * int(request.form.get("shares"))

        #checking if user can afford the deal
        if (amount <= wallet):
            n = db.execute("SELECT username FROM users WHERE id = :userid", userid=session["user_id"])

            #updating portfolio with all the required details of the transaction
            db.execute("INSERT INTO portfolio VALUES (:value1,:value2,:value3,:value4,:value5,:value6)",
             value1 = session["user_id"], value2 = n[0]["username"], value3 = request.form.get(
            "symbol"), value4 = datetime.datetime.now(), value5 = int(request.form.get("shares")),
            value6 = value["price"])

            #deducting the amount spent on purchase from cash
            db.execute("UPDATE users SET cash = cash - :amt WHERE id=:uid",amt=amount,uid=session["user_id"])
            return redirect("/")

        elif amount > wallet:
            return apology("You don't have enough money!!")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show transational history"""
    passbook = db.execute("SELECT * from portfolio WHERE id = :userid", userid = session["user_id"])
    return render_template("history.html", passbook = passbook)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
        username = request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == 'POST':
        value=lookup(request.form.get("symbol"))
        if value == None:
            return apology("Must give correct symbol")
        else:
            return render_template("quoted.html", name=value["name"], price=usd(value["price"]), symbol=value["symbol"])

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == 'POST':

        if not request.form.get("username"):
            return apology("must provide username", 400)

        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("must provide confirmation", 400)

        elif request.form.get("confirmation") != request.form.get("password"):
            return apology("password didn't match", 400)

        hash = generate_password_hash(request.form.get("password"))
        result = db.execute("INSERT INTO users(username,hash) VALUES(:username,:hash)",username = request.form.get("username"),hash = hash)

        if not result:
            return apology("username already exist")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        session.clear()

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    shares = db.execute("SELECT SUM(number_of_shares),symbol FROM portfolio WHERE id =:userid GROUP BY symbol ",userid = session["user_id"])
    if request.method == "POST":
        to_sell = int(request.form.get('shares'))
        for dic in  shares:
            if dic["symbol"] == request.form.get("symbol"):
                possessed_shares = dic["SUM(number_of_shares)"]
                break
        if(to_sell > possessed_shares):
            return apology("You own less number of shares")
        else:
            value = lookup(request.form.get("symbol"))
            amount = to_sell * value["price"]
            n=db.execute("SELECT username FROM users WHERE id = :userid",userid=session["user_id"])
            db.execute("INSERT INTO portfolio VALUES (:value1,:value2,:value3,:value4,:value5,:value6)",value1=session["user_id"],value2=n[0]["username"],value3=request.form.get("symbol"),value4=datetime.datetime.now(),value5 = -1 * to_sell ,value6=value["price"])
            db.execute("UPDATE users SET cash = cash + :amt WHERE id=:uid",amt=amount,uid=session["user_id"])

            return redirect("/")



    else:
        return render_template("sell.html",stock = shares)



@app.route("/add", methods=["GET", "POST"])
@login_required
def addmoney():
    if request.method == 'POST':
        cs = int(request.form.get("money"))
        db.execute("UPDATE users SET cash = cash + :c WHERE id = :userid", c = cs,userid = session["user_id"])
        return redirect("/")
    else:
        return render_template("addmoney.html")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
