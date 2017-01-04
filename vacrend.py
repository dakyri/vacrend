import os
import sys
import click
from flask import Flask, g, jsonify, session, render_template, request, flash, redirect
from sqlite3 import dbapi2 as sqlite3
from flask_oauth2_login import GoogleLogin
from flask_bootstrap import Bootstrap
from sys import stderr

app = Flask(__name__)
Bootstrap(app)

# set up default config and then override this from an environment variable if exists
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'vacrend.db'),
    DEBUG=True,
    SECRET_KEY='CorrectHorseBatteryStaple',
    GOOGLE_LOGIN_REDIRECT_SCHEME="http",
    USERNAME='some_username',
    PASSWORD='some_password',
    GOOGLE_LOGIN_CLIENT_ID='877688205998-agkco59b3esailbp533sddhoh78rg6j5.apps.googleusercontent.com',
    GOOGLE_LOGIN_CLIENT_SECRET='-xMnBunvWnQaPH6iYJ62Mahr'
))

app.config.from_envvar('VACREND_SETTINGS', silent=True)

google_login = GoogleLogin(app)

mock_login = True

@google_login.login_success
def login_success(token, profile):
    """Actions taken on a successul login. Will try to verify the login to a local user database with specific rights"""
    gid = profile.get('email', None)

    if (not gid):
        flash("Expected google id in login response", "error")
        return render_template('main.html');  
    print("Trying to login as "+gid, file=sys.stderr)
    if (not set_login(gid)):
        return render_template('main.html');
    print("Successfully logged in as "+gid, file=sys.stderr)
    return render_view_command(gid)

@google_login.login_failure
def login_failure(e):
    """Actions taken on a failed login """
    set_logout()
    flash(str(e), "error")
    return render_template('main.html');  

def set_logout():
    """Clear record of user id from our session """
    session.pop('logged_in', None)
    session.pop('logged_in_id', None);
    session.pop('logged_in_gid', None);

def set_login(googleid):
    """Add details and rights of a user to our session """
    db = get_db()

    cur = db.execute("select id, rights from users where google_id=?", [googleid])
    row = cur.fetchone()
    if (row):
        flash("Successfully logged in "+googleid)
        session['logged_in_id'] = row[0]       
        session['logged_in_gid'] = googleid       
        session['logged_in'] = row[1] # 0=a viewing user, 1=an editting user, 2=an admin user
        return True;
    else:
        flash(googleid + " not in local user database ", "error")
        session.pop('logged_in', None)
        session.pop('logged_in_id', None)
        session.pop('logged_in_gid', None)
        return False   

def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

def init_db():
    """Initializes the database."""
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()
    print("Database successfully initialized")
    
def add_user_db(gid, level):
    """Inserts or updates the rights of the given user in our database."""
    db = get_db()
    cur = db.execute('update users set rights=? where google_id=?', [level, gid])
    if (cur.rowcount == 0):
        cur = db.execute('insert into users (google_id, rights) values(?, ?)', [gid, level])
    db.commit()
    return cur.rowcount

def del_user_db(gid):
    """Deletes the given user in our database."""
    db = get_db()
    cur = db.execute('delete from users where google_id=?', [gid])
    db.commit()
    return cur.rowcount
    
def add_vacation_db(gid, start, end):
    """Inserts a vacation entry in our database."""
    db = get_db()
    cur = db.execute('insert into vacations (user_id, start_date, end_date, approved) values(?, ?, ?, 0)', [gid, start, end])
    db.commit()
    return cur.rowcount
    
def del_vacation_db(rid):
    """Removes a given vacations entry (designated by rowid) in our database."""
    db = get_db()
    cur = db.execute('delete from vacations where id=?', [rid])
    db.commit()
    return cur.rowcount
    
def approve_vacation_db(rids, val=1):
    """Updates a given vacations entry(s) (designated by array of rowid) in our database."""
    db = get_db()
    args = [val]
    args.extend(rids)
    cur = db.execute('update vacations set approved=? where id in (%s)' % ','.join('?'*len(rids)), args)
    db.commit()
    return cur.rowcount

@app.teardown_appcontext
def teardown_db(exception):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()
        
    
def render_view_command(userid=None):
    """Returns a rendering of a basic view page for a user"""
    db = get_db()
    if (userid):
        cur = db.execute('select id, user_id, start_date, end_date, approved from vacations where user_id=?', [userid])
    else:
        cur = db.execute('select id, user_id, start_date, end_date, approved from vacations')
        
    entries = cur.fetchall()
    return render_template('main.html', entries=entries)

def render_approve_command(status=0,userid=None):
    """Returns a rendering of the basic admin approval page"""
    db = get_db()
    if (userid):
        cur = db.execute('select id, user_id, start_date, end_date, approved from vacations where approved=? and user_id=?', [status, userid])
    else:
        cur = db.execute('select id, user_id, start_date, end_date, approved from vacations where approved=?', [status])
        
    entries = cur.fetchall()
    return render_template('approve.html', title='Vacation Approvals', entries=entries)

def render_requests_command(userid=None):
    """Returns a rendering of a basic admin request browse page """
    db = get_db()
    if (userid):
        cur = db.execute('select id, user_id, start_date, end_date, approved from vacations where user_id=?', [userid])
    else:
        cur = db.execute('select id, user_id, start_date, end_date, approved from vacations')
        
    entries = cur.fetchall()
    return render_template('requests.html', title='Browse Vacation Requests', entries=entries)


def render_users_command(userid=None):
    """Returns a rendering of a basic user admin"""
    db = get_db()
    if (userid):
        cur = db.execute('select google_id, rights from users where google_id=?', [userid])
    else:
        cur = db.execute('select google_id, rights from users')
        
    entries = cur.fetchall()
    return render_template('users.html', title='Administer Users', entries=entries)

@app.cli.command('add')
@click.option('--user', help='a viewing user to add')
@click.option('--employee', help='an editting user to add')
@click.option('--admin', help='an admin user to add')
def cli_add2db(user, employee, admin):
    """Adds a user to the users file either with admin rights or not """
    rows = 0
    if (user):
        rows = add_user_db(user, 0)
        if (rows > 0):
            print ("Successfully inserted user "+user)
    elif (employee):
        rows = add_user_db(employee, 1)
        if (rows > 0):
            print ("Successfully inserted employee "+employee)
    elif (admin):
        rows = add_user_db(admin, 2)
        if (rows > 0):
            print ("Successfully inserted admin "+admin)
    if (rows == 0):
        print ("Nothing to do here")

@app.cli.command('del')
@click.option('--gid', help='id of user to remove')
def cli_del2db(gid):
    """Removes a user from the users file according to google_id """
    rows = 0
    if (gid):
        rows = del_user_db(gid)
    if (rows > 0):
        print ("Successfully deleted "+gid)
    else:
        print ("Nothing to do here")

@app.cli.command('initdb')
def cli_initdb():
    """Creates the basic database tables. Run from site directory by calling 'flask initdb' from the CLI."""
    init_db()
    print('Initialized the database.')


@app.route('/view')
@app.route('/')
def index():
    """Main page handler"""
    print(request, file=sys.stderr)
    logged_in = session.get('logged_in', 0)
    if (logged_in):
        return render_view_command(session.get('logged_in_gid', None))
    else:
        return render_template('main.html')


@app.route('/add', methods=['GET', 'POST'])
def add():
    """Handler to accept form data and add to database"""
    print(request, file=sys.stderr)
    logged_in = session.get('logged_in', 0)
    if (logged_in):
        startDate = request.form['startDate']
        endDate = request.form['endDate']
        gid = session.get('logged_in_gid', None)
        if (startDate and endDate):
            add_vacation_db(gid, startDate, endDate)
            flash("Added request for "+startDate+" to "+endDate)
            return render_view_command(gid)
        else:
            flash("expecting a valid start and end date", "error")
            return render_view_command(gid)
    else:
        flash("you must login first", "error")
        return render_template('main.html')


@app.route('/approve', methods=['GET', 'POST'])
def approve():
    """Handler to present the approval page to the admin"""
    print(request, file=sys.stderr)
    logged_in = session.get('logged_in', 0)
    if (logged_in >= 2):
        f = request.form
        if (f):
            approvals = []
            disprovals = []
            pendings = []
            for key in f.keys():
                ka = key.split('.')
                if (len(ka) >= 2):
                    rowid = int(ka[1])
                    l = f.getlist(key)
                    if (len(l) > 0):
                        what = int(l[0])
                        print(l[0]+", "+key+", "+str(rowid), file=sys.stderr)
                        if (what < 0):
                            disprovals.append(rowid)
                        elif (what > 0):
                            approvals.append(rowid)
                        else:
                            pendings.append(rowid)
            approve_vacation_db(approvals, 1)
            approve_vacation_db(disprovals, -1)
            approve_vacation_db(pendings, 0)
        return render_approve_command(0)
    else:
        flash("you must login as an admin first", "error")
        return render_template('main.html')

@app.route('/requests', methods=['GET', 'POST'])
def requests():
    print(request, file=sys.stderr)
    logged_in = session.get('logged_in', 0)
    if (logged_in >= 2):
        return render_requests_command()
    else:
        flash("you must login as an admin first", "error")
        return render_template('main.html')

@app.route('/users', methods=['GET', 'POST'])
def users():
    print(request, file=sys.stderr)
    logged_in = session.get('logged_in', 0)
    if (logged_in >= 2):
# handle any requests to modify the users here
        return render_users_command()
    else:
        flash("you must login as an admin first", "error")
        return render_template('main.html')
    
@app.route('/logout')
def logout():
    """Handler for site logout. We should probably also log out from google here"""
    logged_in = session.get('logged_in', 0)
    gid = session.get('logged_in_gid', None)
    if (logged_in):
        set_logout()
        if (gid):
            flash("Successfully logged out "+gid)
    return render_template('layout.html')

@app.route('/login')
def login():
    if (mock_login):
        flash("Mock login")
        mock_id = "dakyri@gmail.com"
        session['logged_in_id'] = 2       
        session['logged_in_gid'] = mock_id     
        session['logged_in'] = 2 # 0=a viewing user, 1=an editting user, 2=an admin user
        return render_view_command(mock_id);
    return redirect(google_login.authorization_url(), 302)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
