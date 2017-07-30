# from __future__ import unicode_literals

import os
import yaml
import tweepy
from flask import Flask
from pymongo import MongoClient
from datetime import datetime, timedelta
from flask import render_template, url_for, request, redirect



app = Flask(__name__)
this_path = os.path.dirname(os.path.realpath(__file__))
SETTINGS = yaml.load(open(os.path.join(this_path, 'settings.yml')))

ROUTE_PREFIX = SETTINGS['app-prefix']

@app.route(ROUTE_PREFIX + '/')
def welcome():
    return render_template('welcome.html')

@app.route(ROUTE_PREFIX + '/gototwitter')
def gototwitter():
    respondent_id = request.args.get('respondent_id', 'NA').strip()
    if respondent_id == ' ':
        respondent_id = 'NA'
        return render_template('welcome_please_fill.html')

    if 'approved-ids-filename' in SETTINGS:
        if os.path.isfile(SETTINGS['approved-ids-filename']):
            with open(SETTINGS['approved-ids-filename'], 'rt') as f:
                allowed_ids = set([l.strip() for l in f])
            if respondent_id.strip() not in allowed_ids:
                return render_template('welcome_wrong_id.html')
    

    callback_url = SETTINGS['url'] + url_for('callback_with_id', respondent_id=respondent_id)

    auth = tweepy.OAuthHandler(SETTINGS['twitter']['consumer-key'].decode(),
                               SETTINGS['twitter']['consumer-secret'].decode(),
                               callback_url)


    try: 
        #get the request tokens
        redirect_url= auth.get_authorization_url()

        db = get_db_connection()
        db.users.insert_one({
            'respondent_id': respondent_id,
            'timestamp': datetime.now(),
            'request_token': auth.request_token
            })
    except tweepy.TweepError:
        return redirect(url_for('welcome'))

    #this is twitter's url for authentication
    return redirect(redirect_url)
        
@app.route(ROUTE_PREFIX + '/welcome/<respondent_id>')
def welcome_with_id(respondent_id):
    return render_template('welcome.html', respondent_id=respondent_id)

@app.route(ROUTE_PREFIX + '/callback/<respondent_id>')
def callback_with_id(respondent_id): 
    if 'denied' in request.args:
        db = get_db_connection()
        u = db.users.find_one({'request_token.oauth_token': request.args['denied']})

        db.users.update_one({'request_token.oauth_token': request.args['denied']},
                            {'$set': {'denied': datetime.now()}})
        return redirect(url_for('thanks_for_nothing'))
    else:

        verifier= request.args['oauth_verifier']

        auth = tweepy.OAuthHandler(SETTINGS['twitter']['consumer-key'], SETTINGS['twitter']['consumer-secret'])

        db = get_db_connection()
        u = db.users.find_one({'request_token.oauth_token': request.args['oauth_token']})

        auth.request_token = u['request_token']

        try:
            auth.get_access_token(verifier)
        except tweepy.TweepError:
            return redirect(url_for('thanks_for_nothing')) # ? 

        api = tweepy.API(auth)
        me = api.me()._json
        db.users.update_one({'request_token.oauth_token': request.args['oauth_token']},
                            {'$set': {
                                'user': me,
                                'access_token': auth.access_token,
                                'access_token_secret': auth.access_token_secret
                                },
                             '$unset': {'request_token': ''}
                            })

        return redirect(url_for('thanks', userid=me['id']))

@app.route(ROUTE_PREFIX + '/thanks/<userid>')
def thanks(userid):
    name = get_db_connection().users.find_one({'user.id_str': str(userid)})['user']['name']
    return render_template("thanks.html", name=name)

@app.route(ROUTE_PREFIX + '/thank_you')
def thanks_for_nothing():
    return render_template('thanks_for_nothing.html')

@app.route(ROUTE_PREFIX + '/privacy')
def privacy():
    return render_template("privacy.html")


def get_db_connection():
    cl = MongoClient(SETTINGS['database']['host'], SETTINGS['database']['port'])
    db = cl[SETTINGS['database']['db']]
    if SETTINGS['database']['username'] and SETTINGS['database']['password']:
        db.authenticate(SETTINGS['database']['username'], SETTINGS['database']['password'])
    return db

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

