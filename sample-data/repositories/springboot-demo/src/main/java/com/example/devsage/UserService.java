package com.example.devsage;

/** Business service used by the DevSage sample dataset. */
public class UserService {

    public UserController.UserDto findUser(long id) {
        return new UserController.UserDto(id, "Sample User");
    }
}

