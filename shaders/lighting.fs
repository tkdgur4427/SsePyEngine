
precision highp float;

// raylib predefined shader variables:
// - https://github.com/raysan5/raylib/wiki/raylib-default-shader
in vec2 fragTexCoord;

// user-defined variables
uniform sampler2D GBufferColor;
uniform sampler2D GBufferNormal;
uniform sampler2D GBufferDepth;
uniform sampler2D SSAO;

uniform vec3 CameraPosition;
uniform mat4 CameraInvViewProjection;
uniform vec3 LightDirection;
uniform vec3 SunColor;
uniform float SunIntensity;
uniform vec3 SkyColor;
uniform float SkyIntensity;
uniform float GroundIntensity;
uniform float AmbientIntensity;
uniform float Exposure;
uniform float CameraClipNear;
uniform float CameraClipFar;

out vec4 finalColor;

#define PI 3.14159265358979323846264338327950288

vec3 ToGamma(in vec3 Color)
{
    return vec3(pow(Color.x, 2.2), pow(Color.y, 2.2), pow(Color.z, 2.2));
}

vec3 FromGamma(in vec3 Color)
{
    return vec3(pow(Color.x, 1.0 / 2.2), pow(Color.y, 1.0 / 2.2), pow(Color.z, 1.0 / 2.2));
}

float LinearDepth(float Depth, float Near, float Far)
{
    return (2.0 * Near) / (Far + Near - Depth * (Far - Near));
}

float NonLinearDepth(float Depth, float Near, float Far)
{
    return (((2.0 * Near) / Depth) - Far - Near) / (Near - Far);
}

void main()
{
    // if depth is in-infinite, discard a pixel
    float Depth = texture(GBufferDepth, fragTexCoord).r;
    if (Depth == 1.0f) { discard; }

    // unpack GBuffer
    vec4 ColorAndSpecular = texture(GBufferColor, fragTexCoord);
    vec4 NormalAndGlossiness = texture(GBufferNormal, fragTexCoord);
    vec3 PositionClip = vec3(fragTexCoord, NonLinearDepth(Depth, CameraClipNear, CameraClipFar)) * 2.0f - 1.0f;
    vec4 PixelPositionHomo = CameraInvViewProjection * vec4(PositionClip, 1.0);
    vec3 PixelPosition = PixelPositionHomo.xyz / PixelPositionHomo.w;
    vec3 PixelNormal = NormalAndGlossiness.xyz * 2.0f - 1.0f;
    vec4 SSAOData = texture(SSAO, fragTexCoord);
    vec3 Albedo = ColorAndSpecular.rgb;
    float Specularity = ColorAndSpecular.a;
    float Glossiness = NormalAndGlossiness.a * 100.0f;
    float SunShadow = SSAOData.g;
    float AmbientShadow = SSAOData.r;
    
    // compute lighting
    vec3 EyeDirection = normalize(PixelPosition - CameraPosition);
    vec3 LightSunColor = FromGamma(SunColor);
    vec3 LightSunHalf = normalize(-LightDirection - EyeDirection);

    vec3 LightSkyColor = FromGamma(SkyColor);
    vec3 SkyDirection = vec3(0.0f, -1.0f, 0.0f);
    vec3 LightSkyHalf = normalize(-SkyDirection - EyeDirection);

    float SkyFactorDiff = max(dot(PixelNormal, -LightDirection), 0.0);
    float SkyFactorSpec = Specularity * ((Glossiness + 2.0) / (8.0 * PI)) * pow(max(dot(PixelNormal, LightSunHalf), 0.0), Glossiness);

    float GroundFactorDiff = max(dot(PixelNormal, SkyDirection), 0.0);

    // combining:
    vec3 Ambient = AmbientShadow * AmbientIntensity * LightSkyColor * Albedo;
    vec3 Diffuse = SunShadow * SunIntensity * LightSunColor * Albedo * SkyFactorDiff 
                + GroundIntensity * LightSkyColor * Albedo * GroundFactorDiff 
                + SkyIntensity * LightSkyColor * Albedo * SkyFactorDiff;
    float Specular = SunShadow * SunIntensity * SkyFactorSpec + SkyIntensity * SkyFactorSpec;
    
    vec3 Final = Diffuse + Specular + Ambient;
    finalColor = vec4(ToGamma(Exposure * Final), 1.0f);
    gl_FragDepth = NonLinearDepth(Depth, CameraClipNear, CameraClipFar);
}