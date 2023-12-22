from googleapiclient.discovery import build

api_key = "AIzaSyBECY9MrqPahgg1PiC_OnVWssYvZsgFjrU"

def getData_yt():
    youtube = build('youtube', 'v3', developerKey=api_key)
    req = youtube.search().list(part='snippet',
                            q='cara atasi stress',
                            type='video',
                            maxResults=5)
    type(req)
    res = req.execute()
    
    with open("sample.json", "w") as outfile:
        json.dump(dictionary, outfile)
    return res["items"]