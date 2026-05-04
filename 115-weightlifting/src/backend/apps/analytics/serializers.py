from rest_framework import serializers


class SinclairRequestSerializer(serializers.Serializer):
    bodyweight_kg = serializers.FloatField(min_value=0.01)
    total_kg = serializers.FloatField(min_value=0.01)
    gender = serializers.ChoiceField(choices=['M', 'F'])


class RobiRequestSerializer(serializers.Serializer):
    bodyweight_kg = serializers.FloatField(min_value=0.01, max_value=300)
    total_kg = serializers.FloatField(min_value=0.01, max_value=700)
    gender = serializers.ChoiceField(choices=['M', 'F'])

