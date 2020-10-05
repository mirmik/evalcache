import inspect


def arg_with_name(name, func, args, kwargs):
	spec = inspect.getfullargspec(func)

	if name in kwargs:
		finded = kwargs[name]

	else:
		for i in range(0, len(args)):
			if spec.args[i] == name:
				finded = args[i]
				break
		else:
			print("ERROR: Argument {} don`t exist in wrapped_function".format(name))

	return finded


def argument_number(name, func):
	spec = inspect.getfullargspec(func)

	for i in range(0, len(spec.args)):
		if spec.args[i] == name:
			finded = i
			break
	else:
		print("ERROR: Argument {} don`t exist in wrapped_function".format(name))

	return finded

