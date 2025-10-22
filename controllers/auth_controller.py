class AuthController:
    def __init__(self):
        self.current_user: str | None = None

    def login(self, user: str, pw: str) -> bool:
        ok = (user in {"demo", "paper"}) and pw == "1234"
        if ok:
            self.current_user = user
        return ok

    def logout(self):
        user = self.current_user
        self.current_user = None
        return user
