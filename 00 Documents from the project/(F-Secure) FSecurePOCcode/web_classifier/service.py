from argparse import ArgumentParser


class ServiceInterface:
    @staticmethod
    def add_args(argument_parser: ArgumentParser) -> None:
        raise NotImplementedError("The function is not implemented.")
