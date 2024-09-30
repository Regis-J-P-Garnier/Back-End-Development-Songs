from . import app
import os
import json
import pymongo
from flask import jsonify, request, make_response, abort, url_for  # noqa; F401
from pymongo import MongoClient
from bson import json_util
from pymongo.errors import OperationFailure
from pymongo.results import InsertOneResult
from bson.objectid import ObjectId
import sys

SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
json_url = os.path.join(SITE_ROOT, "data", "songs.json")
songs_list: list = json.load(open(json_url))

# client = MongoClient(
#     f"mongodb://{app.config['MONGO_USERNAME']}:{app.config['MONGO_PASSWORD']}@localhost")
mongodb_service = os.environ.get('MONGODB_SERVICE')
mongodb_username = os.environ.get('MONGODB_USERNAME')
mongodb_password = os.environ.get('MONGODB_PASSWORD')
mongodb_port = os.environ.get('MONGODB_PORT')

print(f'The value of MONGODB_SERVICE is: {mongodb_service}')

if mongodb_service == None:
    app.logger.error('Missing MongoDB server in the MONGODB_SERVICE variable')
    # abort(500, 'Missing MongoDB server in the MONGODB_SERVICE variable')
    sys.exit(1)

if mongodb_username and mongodb_password:
    url = f"mongodb://{mongodb_username}:{mongodb_password}@{mongodb_service}"
else:
    url = f"mongodb://{mongodb_service}"


print(f"connecting to url: {url}")

try:
    client = MongoClient(url)
except OperationFailure as e:
    app.logger.error(f"Authentication error: {str(e)}")

db = client.songs
db.songs.drop()
db.songs.insert_many(songs_list)

def parse_json(data):
    return json.loads(json_util.dumps(data))

######################################################################
# INSERT CODE HERE
######################################################################

HTTP_200_OK             = dict(code=200, status="OK")
HTTP_201_CREATED        = dict(code=201, status="CREATED")
HTTP_204_NO_CONTENT     = dict(code=204, status="NO CONTENT")
HTTP_302_FOUND          = dict(code=302, status="FOUND")
HTTP_404_NOT_FOUND      = dict(code=404, status="NOT FOUND")
HTTP_500_SERVER_ERROR   = dict(code=500, status="SERVER ERROR")
def merge_dict(dict_A, dict_B):
    return {**dict_A, **dict_B}

def jsonify_dict(code,data_dict=None):
    if data_dict:
        return jsonify(
                    merge_dict(
                        data_dict,
                        dict(status=code["status"]),
                    )), code["code"]
    return jsonify(
                        dict(status=code["status"]),
                    ),  code["code"]        

@app.route("/health", methods=["GET"])
def health_service():
    """return OK"""
    return jsonify_dict(HTTP_200_OK)

@app.route("/count", methods=["GET"])
def count_service():
    """return length of data"""
    count_documents = None
    try:
        count_documents = db.songs.count_documents({})
    except Exception as err:
        app.logger.error(f"{HTTP_500_SERVER_ERROR['status']} : {err}")
        return  jsonify_dict(HTTP_500_SERVER_ERROR)  
    return jsonify_dict(HTTP_200_OK, dict(count=count_documents))

@app.route("/song", methods=["GET"])
def get_songs():
    """return list of data"""
    list_documents = None
    try:
        list_documents = list(db.songs.find({}))
    except Exception as err:
        app.logger.error(f"{HTTP_500_SERVER_ERROR['status']} : {err}")
        return  jsonify_dict(HTTP_500_SERVER_ERROR)
    return jsonify_dict(HTTP_200_OK, dict(songs=parse_json(list_documents)))

@app.route("/song/<int:id>", methods=["GET"])
def get_song_by_id(id):
    """return song data by id"""
    song = None
    try:
        song = db.songs.find_one(dict(id=id))
    except Exception as err:
        app.logger.error(f"{HTTP_500_SERVER_ERROR['status']} : {err}")
        return  jsonify_dict(HTTP_500_SERVER_ERROR)
    if not song:
        return  jsonify_dict(HTTP_404_NOT_FOUND)
    return jsonify(parse_json(song)), HTTP_200_OK["code"]

@app.route("/song", methods=["POST"])
def create_song():
    """create song by JSON data"""
    song_request_data = request.json
    song_found = None
    try:
        song_found = db.songs.find_one(dict(id=song_request_data["id"]))
    except Exception as err:
        app.logger.error(f"{HTTP_500_SERVER_ERROR['status']} : {err}")
        return  jsonify_dict(HTTP_500_SERVER_ERROR)
    if song_found:
        return jsonify_dict(HTTP_302_FOUND, dict(Message=f"song with id {song_request_data['id']} already present"))
    mongo_inserted_id = None
    try:
        mongo_inserted_id = db.songs.insert_one(song_request_data)
    except Exception as err:
        app.logger.error(f"{HTTP_500_SERVER_ERROR['status']} : {err}")        
    return jsonify_dict(HTTP_201_CREATED, dict(inserted_id=parse_json(mongo_inserted_id.inserted_id)))

@app.route("/song/<int:id>", methods=["PUT"])
def update_song(id):
    """update song by JSON data"""
    # search if soing exist
    song_request_data = request.json
    song_found = None
    try:
        song_found = db.songs.find_one(dict(id=id))
    except Exception as err:
        app.logger.error(f"{HTTP_500_SERVER_ERROR['status']} : {err}")
        return  jsonify_dict(HTTP_500_SERVER_ERROR)
    # if song not found
    if not song_found:
        app.logger.warning("song not found")
        return  jsonify_dict(HTTP_404_NOT_FOUND, dict(message="song not found"))
    # update if song found
    try:
        update_song_set = {"$set": song_request_data}
        update_return = db.songs.update_one(dict(id=id), update_song_set)
    except Exception as err:
        app.logger.error(f"{HTTP_500_SERVER_ERROR['status']} : {err}")
        return  jsonify_dict(HTTP_500_SERVER_ERROR)          
    # look if update modify nothing, something (created)
    if update_return.modified_count == 0:
        app.logger.warning("song found, but nothing updated")
        return jsonify_dict(HTTP_200_OK, dict(message="song found, but nothing updated"))
    try:
        updated_song_found = db.songs.find_one(dict(id=id))
    except Exception as err:
        app.logger.error(f"{HTTP_500_SERVER_ERROR['status']} : {err}")
        return  jsonify_dict(HTTP_500_SERVER_ERROR) 
    return jsonify_dict(HTTP_201_CREATED, parse_json(updated_song_found))

@app.route("/song/<int:id>", methods=["DELETE"])
def delete_song(id):
    """delete song by id"""
    deleted_song_count = None
    try:
        deleted_song_count = db.songs.delete_one(dict(id=id))
    except Exception as err:
        app.logger.error(f"{HTTP_500_SERVER_ERROR['status']} : {err}")
        return  jsonify_dict(HTTP_500_SERVER_ERROR) 
    app.logger.warning(deleted_song_count.deleted_count)
    if deleted_song_count.deleted_count < 1:
        app.logger.warning("song not found")
        return  jsonify_dict(HTTP_404_NOT_FOUND, dict(message="song not found"))
     
    return jsonify_dict(HTTP_204_NO_CONTENT)