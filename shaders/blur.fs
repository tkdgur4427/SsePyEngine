
precision highp float;

in vec2 fragTexCoord;

uniform sampler2D GBufferNormal;
uniform sampler2D GBufferDepth;
uniform sampler2D InputTexture;
uniform mat4 CameraInvProjection;
uniform float CameraClipNear;
uniform float CameraClipFar;
uniform vec2 InvTextureResolution;
uniform vec2 BlurDirection;

float NonLinearDepth(float Depth, float Near, float Far)
{
    return (((2.0 * Near) / Depth) - Far - Near) / (Near - Far);
}

vec3 CameraSpace(vec2 TexCoord, float Depth)
{
    vec4 PositionClip = vec4(vec3(TexCoord, NonLinearDepth(Depth, CameraClipNear, CameraClipFar)) * 2.0 - 1.0, 1.0);
    vec4 Position = CameraInvProjection * PositionClip;
    return Position.xyz / Position.w;
}

float FastNegExp(float X)
{
    return 1.0f / (1.0f + X + 0.48f * X * X + 0.235f * X * X * X);
}

out vec4 finalColor;

void main()
{
    float Depth = texture(GBufferDepth, fragTexCoord).r;
    if (Depth == 1.f) { discard; }

    vec3 BaseNormal = texture(GBufferNormal, fragTexCoord).rgb * 2.0f - 1.0f;
    vec3 BasePosition = CameraSpace(fragTexCoord, Depth);
    
    vec4 TotalColor = vec4(0.0f, 0.0f, 0.0f, 0.0f);
    float TotalWeight = 0.0f;
    float Stride = 2.0f;

    for (int X = -3; X <= 3; ++X)
    {
        vec2 SampleTexCoord = fragTexCoord + float(X) * Stride * BlurDirection * InvTextureResolution;
        vec4 SampleColor = texture(InputTexture, SampleTexCoord);
        vec3 SampleNormal = texture(GBufferNormal, SampleTexCoord).rgb * 2.0f - 1.0f;
        vec3 SamplePosition = CameraSpace(SampleTexCoord, texture(GBufferDepth, SampleTexCoord).r);
        vec3 DiffPosition = (SamplePosition - BasePosition) / 0.05f;

        float WeightPosition = FastNegExp(dot(DiffPosition, DiffPosition));
        float WeightNormal = max(dot(SampleNormal, BaseNormal), 0.f);

        float Weight = WeightPosition * WeightNormal;
        TotalColor += Weight * SampleColor;
        TotalWeight += Weight;
    }

    finalColor = TotalColor / TotalWeight;
}