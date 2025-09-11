class Config:
    def __init__(
        self,
        admins_list,
        super_admin_id,
        staff_chat_id=None,
        assessment_form_link=None,
        ga_chat_id=None,
        banned_users=[],
    ):
        self.super_admin_id = super_admin_id
        self.admins_list = admins_list
        self.staff_chat_id = staff_chat_id
        self.assessment_form_link = assessment_form_link
        self.ga_chat_id = ga_chat_id
        self.banned_users = banned_users

    def as_dict(self):
        return {
            "super_admin_id": self.super_admin_id,
            "admins_list": self.admins_list,
            "staff_chat_id": self.staff_chat_id,
            "assessment_form_link": self.assessment_form_link,
            "ga_chat_id": self.ga_chat_id,
            "banned_users": self.banned_users,
        }
