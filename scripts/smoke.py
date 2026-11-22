import sys, time; sys.path.insert(0, '.')
from nosedive.llm import chat
from nosedive.env import RATING_SCHEMA
for m in sys.argv[1:]:
    t=time.time()
    p, raw, meta = chat(m, "You are an agent. Respond only with JSON.", "Rate your partner who stole from you 1-5 stars. JSON keys: private_thoughts, stars, public_comment.", max_tokens=150, schema=RATING_SCHEMA)
    print(m, round(time.time()-t,1), meta.get('usage'), p if p else raw[:300], meta.get('error'), flush=True)
