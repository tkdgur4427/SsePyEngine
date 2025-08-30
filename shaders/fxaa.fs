precision highp float;

in vec2 fragTexCoord;

uniform sampler2D InputTexture;
uniform vec2 InvTextureResolution;

out vec4 finalColor;

void main()
{
    const float SpanMax = 4.0;
    const float ReduceAmount = 1.0 / 4.0;
    const float ReduceMin = (1.0 / 64.0);

    vec3 Luma = vec3(0.299, 0.587, 0.114);
    float LumaNW = dot(texture(InputTexture, fragTexCoord + (vec2(-1.0, -1.0) * InvTextureResolution)).rgb, Luma);
    float LumaNE = dot(texture(InputTexture, fragTexCoord + (vec2( 1.0, -1.0) * InvTextureResolution)).rgb, Luma);
    float LumaSW = dot(texture(InputTexture, fragTexCoord + (vec2(-1.0,  1.0) * InvTextureResolution)).rgb, Luma);
    float LumaSE = dot(texture(InputTexture, fragTexCoord + (vec2( 1.0,  1.0) * InvTextureResolution)).rgb, Luma);
    float LumaMI = dot(texture(InputTexture, fragTexCoord).rgb, Luma);

    float LumaMin = min(LumaMI, min(min(LumaNW, LumaNE), min(LumaSW, LumaSE)));
    float LumaMax = max(LumaMI, max(max(LumaNW, LumaNE), max(LumaSW, LumaSE)));

    vec2 Direction = vec2(
        -((LumaNW + LumaNE) - (LumaSW + LumaSE)),
        +((LumaNW + LumaSW) - (LumaNE + LumaSE)));
    
    float DirectionReduce = max((LumaNW + LumaNE + LumaSW + LumaSE) * (0.25 * ReduceAmount), ReduceMin);
    float DirectionRcpMin = 1.0 / (min(abs(Direction.x), abs(Direction.y)) + DirectionReduce);

    Direction = min(vec2(SpanMax, SpanMax), max(vec2(-SpanMax, -SpanMax), Direction * DirectionRcpMin)) * InvTextureResolution;

    vec3 Rgba0 = texture(InputTexture, fragTexCoord + Direction * (1.0 / 3.0 - 0.5)).rgb;
    vec3 Rgba1 = texture(InputTexture, fragTexCoord + Direction * (2.0 / 3.0 - 0.5)).rgb;
    vec3 Rgba2 = texture(InputTexture, fragTexCoord + Direction * (0.0 / 3.0 - 0.5)).rgb;
    vec3 Rgba3 = texture(InputTexture, fragTexCoord + Direction * (3.0 / 3.0 - 0.5)).rgb;

    vec3 Rgb0 = (1.0 / 2.0) * (Rgba0 + Rgba1);
    vec3 Rgb1 = Rgb0 * (1.0 / 2.0) + (1.0 / 4.0) * (Rgba2 + Rgba3);

    float LumaB = dot(Rgb1, Luma);
    finalColor.rgb = (LumaB < LumaMin) || (LumaB > LumaMax) ? Rgb0 : Rgb1;
}
