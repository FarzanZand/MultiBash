// Skybox: vertical gradient + chunky pixelated clouds (Megabonk-like blue dusk sky).
Shader "MultiBash/PixelSky"
{
    Properties
    {
        _TopColor ("Top", Color) = (0.13, 0.42, 0.72, 1)
        _HorizonColor ("Horizon", Color) = (0.32, 0.62, 0.78, 1)
        _BottomColor ("Below Horizon", Color) = (0.18, 0.36, 0.45, 1)
        _CloudColor ("Clouds", Color) = (0.55, 0.75, 0.88, 1)
        _CloudScale ("Cloud Scale", Float) = 3.0
        _CloudCover ("Cloud Cover", Range(0, 1)) = 0.45
        _Pixel ("Pixel Size (lower = chunkier)", Float) = 90
        _Speed ("Cloud Speed", Float) = 0.004
    }
    SubShader
    {
        Tags { "Queue"="Background" "RenderType"="Background" "PreviewType"="Skybox" }
        Cull Off ZWrite Off
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            half4 _TopColor, _HorizonColor, _BottomColor, _CloudColor;
            float _CloudScale, _CloudCover, _Pixel, _Speed;

            struct A { float4 pos : POSITION; };
            struct V { float4 pos : SV_POSITION; float3 dir : TEXCOORD0; };

            V vert (A v) { V o; o.pos = TransformObjectToHClip(v.pos.xyz); o.dir = v.pos.xyz; return o; }

            float hash(float2 p) { return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453); }
            float noise(float2 p)
            {
                float2 i = floor(p), f = frac(p);
                f = f * f * (3 - 2 * f);
                return lerp(lerp(hash(i), hash(i + float2(1, 0)), f.x), lerp(hash(i + float2(0, 1)), hash(i + float2(1, 1)), f.x), f.y);
            }
            float fbm(float2 p) { float s = 0, a = 0.5; for (int k = 0; k < 4; k++) { s += noise(p) * a; p *= 2.1; a *= 0.5; } return s; }

            half4 frag (V i) : SV_Target
            {
                float3 d = normalize(i.dir);
                float h = d.y;
                half3 col = h > 0 ? lerp(_HorizonColor.rgb, _TopColor.rgb, pow(saturate(h), 0.6)) : lerp(_HorizonColor.rgb, _BottomColor.rgb, saturate(-h * 4));
                if (h > 0.02)
                {
                    // project onto a cloud plane and quantize -> pixel clouds
                    float2 uv = d.xz / (h + 0.15) * _CloudScale;
                    uv = floor(uv * _Pixel / _CloudScale) / (_Pixel / _CloudScale);
                    uv += _Time.y * _Speed * float2(1, 0.3);
                    float c = fbm(uv * 0.35);
                    float m = step(1 - _CloudCover, c) * saturate((h - 0.02) * 6);
                    float m2 = step(1 - _CloudCover * 0.75, c);
                    col = lerp(col, _CloudColor.rgb, m * 0.65);
                    col = lerp(col, _CloudColor.rgb * 1.15, m2 * m * 0.4);
                }
                return half4(col, 1);
            }
            ENDHLSL
        }
    }
}
