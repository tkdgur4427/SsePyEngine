// raylib predefined shader variables:
// - https://github.com/raysan5/raylib/wiki/raylib-default-shader
in vec3 vertexPosition;
in vec2 vertexTexCoord;

uniform mat4 mvp;

out vec2 fragTexCoord;

void main()
{
    fragTexCoord = vertexTexCoord;
    gl_Position = mvp * vec4(vertexPosition, 1.0f);
}
