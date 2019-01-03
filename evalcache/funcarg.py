def arg_with_name(name, func, args, kwargs):
	if self.generic.field in self.kwargs:
			path = self.kwargs[self.generic.field]

	else:
		for i in range(0, len(self.args)):
			if spec.args[i] == self.generic.field:
				path = self.args[i]
				break
		else:
			print("ERROR: Argument {} don`t exist in wrapped_function".format(self.generic.field))
