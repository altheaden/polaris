class Step:
    def __init__(self, name):
        self.name: str = name
        self.inputs: list[str] = list()
        self.outputs: list[str] = list()

    def add_input_file(self, filename):
        self.inputs.append(filename)

    def add_input_files(self, filenames):
        self.inputs.extend(filenames)

    def add_output_file(self, filename):
        self.outputs.append(filename)

    def add_output_files(self, filenames):
        self.outputs.extend(filenames)
