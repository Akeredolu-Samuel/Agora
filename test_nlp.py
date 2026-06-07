import nlp
import os

from dotenv import load_dotenv
load_dotenv()

print(nlp.parse_intent("save 0x6362880df2E6bba30e15794B8A981CaB3A8a6825 as david"))
print(nlp.parse_intent("pay 1 0x6362880df2E6bba30e15794B8A981CaB3A8a6825"))
