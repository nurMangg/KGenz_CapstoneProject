from googleapiclient.discovery import build
import json

api_key = "AIzaSyBECY9MrqPahgg1PiC_OnVWssYvZsgFjrU"


youtube = build('youtube', 'v3', developerKey=api_key)
req = youtube.search().list(part='snippet',
                            q='cara atasi stress',
                            type='video',
                            maxResults=5)
type(req)
res = req.execute()
with open("api/data_youtube.json", "w") as outfile:
    json.dump(res, outfile)
print(res['items'])