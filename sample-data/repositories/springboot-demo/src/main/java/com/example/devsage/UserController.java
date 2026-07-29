package com.example.devsage;

/** Minimal controller used by the DevSage sample dataset. */
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    public UserDto getUser(long id) {
        return userService.findUser(id);
    }

    public record UserDto(long id, String name) {
    }
}

