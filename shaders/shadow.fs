
precision highp float;

uniform float LightClipNear;
uniform float LightClipFar;

float LinearDepth(float Depth, float Near, float Far)
{
    return (2.0 * Near) / (Far + Near - Depth * (Far - Near));
}

void main()
{
    gl_FragDepth = LinearDepth(gl_FragCoord.z, LightClipNear, LightClipFar);
}
