// MultiBash "Megabonk-style" lit shader.
// Base color comes from the shared palette texture (UV points at a palette cell).
// The palette cell's ALPHA picks a pixel-art detail pattern that is projected onto the mesh
// (object-space, dominant axis, point filtered) so flat low-poly faces get chunky pixel texture:
//   alpha 1.00 = noise   0.75 = bricks   0.50 = leaves/grass   0.25 = wood grain   0.125 = glow (emissive)   0 = flat
// Supports main light + shadows, additional lights, ambient, fog, base color tint and emission (hit flash).
Shader "MultiBash/PixelLit"
{
    Properties
    {
        _BaseMap ("Palette", 2D) = "white" {}
        _BaseColor ("Tint", Color) = (1,1,1,1)
        _DetailAtlas ("Detail Atlas (2x2 patterns)", 2D) = "gray" {}
        _DetailTile ("Detail Tile Size (meters)", Float) = 1.6
        _DetailStrength ("Detail Strength", Range(0, 1.5)) = 0.75
        _EmissionColor ("Emission", Color) = (0,0,0,1)
        _Wrap ("Light Wrap (softness)", Range(0, 1)) = 0.35
        _ShadowTint ("Shadow Tint", Color) = (0.45, 0.55, 0.75, 1)
    }

    SubShader
    {
        Tags { "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float4 _BaseMap_ST;
            half4 _BaseColor;
            float4 _DetailAtlas_ST;
            float _DetailTile;
            half _DetailStrength;
            half4 _EmissionColor;
            half _Wrap;
            half4 _ShadowTint;
        CBUFFER_END

        TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);
        TEXTURE2D(_DetailAtlas); SAMPLER(sampler_DetailAtlas);

        // pick the detail value for this pixel: dominant-axis object-space projection into one atlas cell
        half SampleDetail(float3 posOS, float3 normalOS, half pattern)
        {
            if (pattern < 0.19) return 1.0; // flat or glow
            float3 an = abs(normalOS);
            float2 p = an.x > an.y && an.x > an.z ? posOS.zy : (an.y > an.z ? posOS.xz : posOS.xy);
            float2 cellUV = frac(p / _DetailTile);
            // pattern -> atlas cell (2x2): 1=noise(0,1) 0.75=brick(1,1) 0.5=leaves(0,0) 0.25=grain(1,0)
            float2 cell = pattern > 0.875 ? float2(0, 1) : pattern > 0.625 ? float2(1, 1) : pattern > 0.375 ? float2(0, 0) : float2(1, 0);
            half v = SAMPLE_TEXTURE2D(_DetailAtlas, sampler_DetailAtlas, (cell + cellUV) * 0.5).r;
            return lerp(1.0, 0.55 + v * 0.75, _DetailStrength);
        }
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode"="UniversalForward" }

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile _ _FORWARD_PLUS _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fog
            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 positionWS : TEXCOORD1;
                float3 normalWS : TEXCOORD2;
                float3 positionOS : TEXCOORD3;
                float3 normalOS : TEXCOORD4;
                half fogFactor : TEXCOORD5;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            Varyings vert (Attributes v)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                VertexPositionInputs pos = GetVertexPositionInputs(v.positionOS.xyz);
                o.positionCS = pos.positionCS;
                o.positionWS = pos.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.positionOS = v.positionOS.xyz;
                o.normalOS = v.normalOS;
                o.uv = TRANSFORM_TEX(v.uv, _BaseMap);
                o.fogFactor = ComputeFogFactor(pos.positionCS.z);
                return o;
            }

            half4 frag (Varyings i) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                half4 pal = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv);
                half3 albedo = pal.rgb * _BaseColor.rgb * SampleDetail(i.positionOS, i.normalOS, pal.a);
                float3 n = normalize(i.normalWS);

                float4 shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                Light mainLight = GetMainLight(shadowCoord);
                half ndl = saturate((dot(n, mainLight.direction) + _Wrap) / (1 + _Wrap));
                half atten = mainLight.shadowAttenuation * mainLight.distanceAttenuation;
                half3 lit = mainLight.color * ndl * atten;
                // tinted shadows (blue-ish like the reference) instead of plain darkening
                half3 ambient = SampleSH(n) * lerp(_ShadowTint.rgb, 1, 0.5);
                half3 color = albedo * (ambient + lit);

                #if defined(_ADDITIONAL_LIGHTS)
                InputData inputData = (InputData)0;
                inputData.positionWS = i.positionWS;
                inputData.normalWS = n;
                inputData.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
                uint lightCount = GetAdditionalLightsCount();
                LIGHT_LOOP_BEGIN(lightCount)
                    Light l = GetAdditionalLight(lightIndex, i.positionWS, half4(1, 1, 1, 1));
                    half d = saturate(dot(n, l.direction) * 0.5 + 0.5);
                    color += albedo * l.color * d * l.distanceAttenuation * l.shadowAttenuation;
                LIGHT_LOOP_END
                #endif

                // "glow" palette cells (alpha ~0.125) are emissive so bloom picks them up
                half glow = (pal.a > 0.06 && pal.a < 0.19) ? 1.0 : 0.0;
                color = lerp(color, albedo * 2.4, glow);
                color += _EmissionColor.rgb;
                color = MixFog(color, i.fogFactor);
                return half4(color, 1);
            }
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode"="ShadowCaster" }
            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull Back

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; UNITY_VERTEX_INPUT_INSTANCE_ID };

            float4 vert (Attributes v) : SV_POSITION
            {
                UNITY_SETUP_INSTANCE_ID(v);
                float3 ws = TransformObjectToWorld(v.positionOS.xyz);
                float3 nws = TransformObjectToWorldNormal(v.normalOS);
                #if _CASTING_PUNCTUAL_LIGHT_SHADOW
                    float3 ld = normalize(_LightPosition - ws);
                #else
                    float3 ld = _LightDirection;
                #endif
                float4 cs = TransformWorldToHClip(ApplyShadowBias(ws, nws, ld));
                #if UNITY_REVERSED_Z
                    cs.z = min(cs.z, UNITY_NEAR_CLIP_VALUE);
                #else
                    cs.z = max(cs.z, UNITY_NEAR_CLIP_VALUE);
                #endif
                return cs;
            }

            half4 frag () : SV_Target { return 0; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode"="DepthOnly" }
            ZWrite On
            ColorMask R

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            struct Attributes { float4 positionOS : POSITION; UNITY_VERTEX_INPUT_INSTANCE_ID };
            float4 vert (Attributes v) : SV_POSITION { UNITY_SETUP_INSTANCE_ID(v); return TransformObjectToHClip(v.positionOS.xyz); }
            half frag () : SV_Target { return 0; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode"="DepthNormals" }
            ZWrite On

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; float3 normalWS : TEXCOORD0; };
            Varyings vert (Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                return o;
            }
            half4 frag (Varyings i) : SV_Target { return half4(normalize(i.normalWS), 0); }
            ENDHLSL
        }
    }
    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}
