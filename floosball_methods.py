from random import randint
import json
import floosball_team as FloosTeam
import floosball_player as FloosPlayer
import floosball_game as FloosGame
import floosball_player as FloosPlayer


def getConfig():
    fileObjext = open("config.json", "r")
    jsonContent = fileObjext.read()
    config = json.loads(jsonContent)
    fileObjext.close()
    return config

def saveConfig(value, key1, key2):
    fileObjext = open("config.json", "r")
    jsonContent = fileObjext.read()
    config = json.loads(jsonContent)
    fileObjext.close()

    if key2 is None:
        config[key1] = value
    else:
        config[key1][key2] = value

    fileObjext = open("config.json", "w+")
    fileObjext.write(json.dumps(config, indent=4))
    fileObjext.close()

def _prepare_for_serialization(obj):
    serialized_dict = dict()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if v != 0:
                if isinstance(v, list):
                    tempDict = {}
                    y = 0
                    for item in v:
                        y += 1
                        tempDict[y] = _prepare_for_serialization(item)
                    serialized_dict[k] = tempDict
                elif isinstance(v, dict):
                    tempDict = {}
                    for a, b in v.items():
                        if isinstance(b, dict):
                            tempDict2 = {}
                            for c, d in b.items():
                                if isinstance(d, dict):
                                    tempDict3 = {}
                                    for e, f in d.items():
                                        if isinstance(f, list):
                                            x = 0
                                            for item in f:
                                                x += 1
                                                tempDict3[x] = _prepare_for_serialization(item)
                                        elif isinstance(d, FloosPlayer.Player):
                                            tempDict3[e] = f.name
                                        elif isinstance(b, FloosTeam.Team):
                                            tempDict3[e] = f.name
                                        else:
                                            tempDict3[e] = f.name if isinstance(f, FloosPlayer.Position) else f
                                    tempDict2[c] = tempDict3
                                if isinstance(d, list):
                                    z = 0
                                    for item in d:
                                        z += 1
                                        tempDict2[z] = _prepare_for_serialization(item)
                                elif isinstance(d, FloosPlayer.Player):
                                    tempDict2[c] = d.name
                                elif isinstance(d, FloosTeam.Team):
                                    tempDict2[c] = d.name
                                elif isinstance(v, FloosPlayer.PlayerTier):
                                    tempDict2[c] = v.name
                                elif isinstance(d, FloosPlayer.PlayerAttributes):
                                    tempDict2[c] = _prepare_for_serialization(d)
                                else:
                                    tempDict2[c] = d.name if isinstance(d, FloosPlayer.Position) else d
                            tempDict[a] = tempDict2
                        elif isinstance(b, list):
                            y = 0
                            for item in b:
                                y += 1
                                tempDict[y] = _prepare_for_serialization(item)
                        elif isinstance(b, FloosPlayer.Player):
                            tempDict[a] = b.name
                        elif isinstance(b, FloosTeam.Team):
                            tempDict[a] = b.name
                        elif isinstance(v, FloosPlayer.PlayerTier):
                            tempDict[a] = v.name
                        elif isinstance(b, FloosPlayer.PlayerAttributes):
                            tempDict[a] = _prepare_for_serialization(b)
                        else:
                            tempDict[a] = b.name if isinstance(b, FloosPlayer.Position) else b
                    serialized_dict[k] = tempDict
                else: 
                    if isinstance(v, FloosPlayer.Position):
                        serialized_dict[k] = v.name 
                    elif isinstance(v, FloosPlayer.PlayerTier):
                        serialized_dict[k] = v.name
                    elif isinstance(v, FloosGame.PlayType):
                        serialized_dict[k] = v.name
                    elif isinstance(v, FloosTeam.Team):
                        serialized_dict[k] = v.name
                    elif isinstance(v, FloosPlayer.PlayerAttributes):
                        serialized_dict[k] = _prepare_for_serialization(v)
                    else:
                        serialized_dict[k] = v
    elif isinstance(obj, list):
        tempDict = {}
        y = 0
        for item in obj:
            y += 1
            tempDict[y] = _prepare_for_serialization(item)
        serialized_dict[y] = tempDict
    else:
        for k, v in obj.__dict__.items():
            if v != 0:
                if isinstance(v, list):
                    tempDict = {}
                    y = 0
                    for item in v:
                        y += 1
                        tempDict[y] = _prepare_for_serialization(item)
                    serialized_dict[k] = tempDict
                elif isinstance(v, dict):
                    tempDict = {}
                    for a, b in v.items():
                        if isinstance(b, FloosPlayer.Player):
                            tempDict[a] = _prepare_for_serialization(b)
                        else:
                            tempDict[a] = b.name if isinstance(b, FloosPlayer.Position) else b
                    serialized_dict[k] = tempDict
                else: 
                    if isinstance(v, FloosPlayer.Position):
                        serialized_dict[k] = v.name 
                    elif isinstance(v, FloosPlayer.PlayerTier):
                        serialized_dict[k] = v.name 
                    elif isinstance(v, FloosGame.PlayType):
                        serialized_dict[k] = v.name
                    elif isinstance(v, FloosTeam.Team):
                        serialized_dict[k] = v.name
                    elif isinstance(v, FloosPlayer.PlayerAttributes):
                        serialized_dict[k] = _prepare_for_serialization(v)
                    else:
                        serialized_dict[k] = v
    return serialized_dict                    


def getStat(min, max, weight):
    x = randint(min,max)
    if weight == 1:
        if x >= 95:
            return randint(95, 100)
        elif x < 95 and x >= 75:
            return randint(85, 94)
        elif x < 75 and x >= 25:
            return randint(75, 84)
        else:
            return randint(65, 74)
    else:
        return x




def getPower(x, y):
    z = 1
    while z < y:
        if (x**z) == y:
            return z
        else:
            z += 1
    return 0