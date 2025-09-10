class User:
    def __init__(
        self, id: int, serial_number: int, filled_form: bool, custom_name=None
    ):
        self.id = id
        self.serial_number = serial_number
        self.filled_form = filled_form
        self.custom_name = custom_name

    def as_dict(self):
        return {
            "_id": self.id,
            "serial_number": self.serial_number,
            "filled_form": self.filled_form,
            "custom_name": self.custom_name,
        }
