class FormatoDeChatInvalido(Exception):
    """Un archivo de exportación de chat no cumple el formato esperado (F-02)."""

    def __init__(self, path, motivo: str) -> None:
        super().__init__(f"{path}: {motivo}")
        self.path = path
        self.motivo = motivo
