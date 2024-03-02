from .logger import timeLog
import json, os, appdirs
from pyee import AsyncIOEventEmitter

configEvent = AsyncIOEventEmitter()

def mergeConfigRecursively(template, raw):
    for key in template:
        if key not in raw:
            raw[key] = template[key]
        elif type(template[key]) == dict:
            mergeConfigRecursively(template[key], raw[key])

configPath = os.path.join(appdirs.user_config_dir('pinglunji', 'xqe2011'), './config.json')
os.makedirs(appdirs.user_config_dir('pinglunji', 'xqe2011'), exist_ok=True)
# 合并配置文件
jsonConfig = json.load(open(configPath, encoding='utf-8')) if os.path.isfile(configPath) else {}
templateConfig = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../config.template.json'), encoding='utf-8', mode='r'))
mergeConfigRecursively(templateConfig, jsonConfig)
with open(configPath, encoding='utf-8', mode='w') as f:
        json.dump(jsonConfig, f, ensure_ascii=False, indent=4)
timeLog(f'[Config] Loaded json config: {json.dumps(jsonConfig, ensure_ascii=False)}')

async def updateJsonConfig(config):
    global jsonConfig
    oldConfig = jsonConfig
    jsonConfig = config
    with open(configPath, encoding='utf-8', mode='w') as f:
        json.dump(jsonConfig, f, ensure_ascii=False, indent=4)
    timeLog(f'[Config] Updated json config: {json.dumps(jsonConfig, ensure_ascii=False)}')
    configEvent.emit('update', oldConfig, jsonConfig)

def getJsonConfig():
    global jsonConfig
    return jsonConfig
