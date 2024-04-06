from rest_framework import serializers
from .models import Zapchast, Maxsulot


class ZapchastSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zapchast
        fields = ('id', 'name_uz', 'name_ru', 'image')


class MaxsulotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Maxsulot
        fields = ('zapchast', 'name_uz', 'name_ru', 'description', 'description_ru', 'price', 'brand')
