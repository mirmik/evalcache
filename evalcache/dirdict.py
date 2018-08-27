import os
import pickle

class dirdict:
	def __init__(self, dirpath):
		self.dirpath = dirpath

		if not os.path.exists(dirpath):
			os.mkdir(dirpath)
			self.files = set()
		else:
			lst = os.listdir(dirpath)
			self.files = set(lst)

	def __contains__(self, key):
		return key in self.files

	def __setitem__(self, key, value):
		with open(os.path.join(self.dirpath, key), "wb") as fl:
			pickle.dump(value, fl)
		self.files.add(key)
	
	def __getitem__(self, key):
		with open(os.path.join(self.dirpath, key), "rb") as fl:
			return pickle.load(fl)
			