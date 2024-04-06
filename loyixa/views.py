from datetime import datetime

from django.db.models import QuerySet
from django.http import HttpResponse, JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from loyixa.models import Zapchast, Maxsulot


def list_to_exel(query):
    import xlwt
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = f'attachment; filename={str(datetime.now().date())}.xls'
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet("data")
    row_num = 0
    columns = list(query[0].keys())
    for col_num in range(len(columns)):
        ws.write(row_num, col_num, columns[col_num])
    for obj in query:
        row_num += 1
        row = [obj[field] for field in columns]
        for col_num in range(len(row)):
            ws.write(row_num, col_num, row[col_num])
    wb.save(response)
    return response


def query_to_data(query: QuerySet, request, to_exel=False, to_json=False):
    """
        :param to_json:
        :param to_exel:
        :param request:
        :type query: object

    """
    # sort
    sort_field = request.GET.get('sort')
    if sort_field is not None:
        if sort_field[0] == "-":
            sort_field = sort_field[1:]
            query = query.order_by(f"-{sort_field}")
        else:
            query = query.order_by(sort_field)

    # filter
    for i in request.GET:
        if i.startswith("filter["):
            field = i[7:-1]
            try:
                new_query = query.none()
                for j in request.GET[i].split(","):
                    new_query |= query.filter(**{field: j})
                query = new_query
            except Exception as e:
                if to_json:
                    return {
                        "error": str(e),
                        "status": 400
                    }
                return Response({
                    "error": str(e)
                }, status=400)

    # filter with date
    if "from" in request.GET and "until" in request.GET and "field" in request.GET:
        field = request.GET["field"]
        try:
            query = query.filter(**{f"{field}__gte": request.GET["from"], f"{field}__lte": request.GET["until"]})
        except Exception as e:
            return Response({
                "error": str(e)
            }, status=400)

    # search
    if "search" in request.GET:
        new_query = query.none()
        for field in query.model._meta.fields:
            remove_fields = ["ForeignKey", "DateTimeField", "DateField", "TimeField", "BooleanField"]
            if field.name == "id" or field.get_internal_type() in remove_fields:
                continue
            new_query |= query.filter(**{f"{field.name}__icontains": request.GET["search"]})

        query = new_query

    # search with field
    for i in request.GET:
        if i.startswith("search["):
            field = i[7:-1]
            new_query = query.none()
            all_fields = []
            for i in query.model._meta.fields:
                all_fields.append(i.name)
            if field in all_fields:
                new_query = query.filter(**{f"{field}__icontains": request.GET[f"search[{field}]"]})
            query = new_query


    # pagination
    all_foreign_keys = []
    for field in query.model._meta.fields:
        if field.get_internal_type() == "ForeignKey":
            all_foreign_keys.append(field.name)

    data = {"all_data": query.count()}
    page = int(request.GET.get('page', 1))
    if page < 1:
        page = 1
    per_page = int(request.GET.get('per_page', 10))
    if per_page < 1:
        per_page = 1
    data["page"] = page
    data["per_page"] = per_page
    data["data"] = []
    data["last_page"] = query.count() // per_page + 1
    data["next_page_url"] = ""
    data["prev_page_url"] = ""
    data["foreignKeys"] = all_foreign_keys
    data["from"] = (page - 1) * per_page + 1
    data["to"] = page * per_page
    if data["to"] > data["all_data"]:
        data["to"] = data["all_data"]
    if page > 1:
        data["prev_page_url"] = f"?page={page - 1}&per_page={per_page}"
    if page < data["last_page"]:
        data["next_page_url"] = f"?page={page + 1}&per_page={per_page}"
    query = query.values()[(page - 1) * per_page:page * per_page]
    # include
    if "include" in request.GET:
        new_data = []
        include = request.GET["include"].split(",")
        for i in query:
            for j in include:
                if j in all_foreign_keys:
                    i[j] = query.model._meta.get_field(j).related_model.objects.filter(
                        id=i[j + "_id"]).values()[0] if i[j + "_id"] is not None and query.model._meta.get_field(
                        j).related_model.objects.filter(id=i[j + "_id"]).exists() else None
            new_data.append(i)
        data["data"] = list(new_data)
        if to_json:
            return data
        return Response(data)
    if to_exel:
        return list_to_exel(query)

    data["data"] = list(query)

    if to_json:
        return data

    return Response(data)


class Zapchast_all(APIView):
    @staticmethod
    def get(request):
        return query_to_data(Zapchast.objects.all(), request)

    @staticmethod
    def post(request):
        required = ['name_uz', 'name_ru', 'image']
        arr = {}
        for i in required:
            if i not in request.data:
                return JsonResponse({"status": "Error", "message": f"{i} is required"},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                arr[i] = request.data[i]
        try:
            Zapchast.objects.create(**arr)
        except Exception as e:
            return JsonResponse({"status": "Error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return JsonResponse({"status": "Success", "message": "created"}, status=status.HTTP_201_CREATED)

    @staticmethod
    def delete(request):
        try:
            zapchast_id = request.data.get('zapchast_id')
            zapchast = Zapchast.objects.get(pk=zapchast_id)
        except ValueError:
            return JsonResponse({"status": "Error", "message": "'zapchast_id' must be an integer"},
                                status=status.HTTP_400_BAD_REQUEST)
        except Zapchast.DoesNotExist:
            return JsonResponse({"status": "Error", "message": "Zapchast does not exist"},
                                status=status.HTTP_404_NOT_FOUND)

        try:
            zapchast.delete()
        except Exception as e:
            return JsonResponse({"status": "Error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return JsonResponse({"status": "Success", "message": "deleted"}, status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def put(request):
        try:
            zapchast_id = request.data.get('zapchast_id')
            zapchast = Zapchast.objects.get(pk=zapchast_id)
        except ValueError:
            return JsonResponse({"status": "Error", "message": "'zapchast_id' must be an integer"},
                                status=status.HTTP_400_BAD_REQUEST)
        except Zapchast.DoesNotExist:
            return JsonResponse({"status": "Error", "message": "Zapchast does not exist"},
                                status=status.HTTP_404_NOT_FOUND)

        required = ['name_uz', 'name_ru']
        arr = {}
        for i in required:
            if i not in request.data:
                return JsonResponse({"status": "Error", "message": f"{i} is required"},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                arr[i] = request.data[i]

        try:
            for key, value in arr.items():
                setattr(zapchast, key, value)
            zapchast.save()
        except Exception as e:
            return JsonResponse({"status": "Error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return JsonResponse({"status": "Success", "message": "updated"}, status=status.HTTP_200_OK)


class Maxsulot_all(APIView):
    @staticmethod
    def get(request):
        return query_to_data(Maxsulot.objects.all(), request)

    @staticmethod
    def post(request):
        required = ["zapchast_id", 'name_uz', "name_ru", 'description', "description_ru", 'price', 'brand']
        arr = {}
        for i in required:
            if i not in request.data:
                return JsonResponse({"status": "Error", "message": f"{i} is required"},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                arr[i] = request.data[i]

        try:
            Maxsulot.objects.create(**arr)
        except Exception as e:
            return JsonResponse({"status": "Error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return JsonResponse({"status": "Success", "message": "created"}, status=status.HTTP_201_CREATED)

    @staticmethod
    def put(request):
        try:
            maxsulot_id = request.data.get('maxsulot_id')
            maxsulot = Maxsulot.objects.get(pk=maxsulot_id)
        except ValueError:
            return JsonResponse({"status": "Error", "message": "'maxsulot_id' must be an integer"},
                                status=status.HTTP_400_BAD_REQUEST)
        except Maxsulot.DoesNotExist:
            return JsonResponse({"status": "Error", "message": "Maxsulot does not exist"},
                                status=status.HTTP_404_NOT_FOUND)

        required = ['name_uz', 'name_ru', 'description', 'description_ru', 'price', 'brand']
        arr = {}
        for i in required:
            if i not in request.data:
                return JsonResponse({"status": "Error", "message": f"{i} is required"},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                arr[i] = request.data[i]

        try:
            for key, value in arr.items():
                setattr(maxsulot, key, value)
            maxsulot.save()
        except Exception as e:
            return JsonResponse({"status": "Error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return JsonResponse({"status": "Success", "message": "Maxsulot updated"}, status=status.HTTP_200_OK)

    @staticmethod
    def delete(request):
        try:
            maxsulot_id = request.data.get('maxsulot_id')
            maxsulot = Maxsulot.objects.get(pk=maxsulot_id)
        except ValueError:
            return JsonResponse({"status": "Error", "message": "'maxsulot_id' must be an integer"},
                                status=status.HTTP_400_BAD_REQUEST)
        except Maxsulot.DoesNotExist:
            return JsonResponse({"status": "Error", "message": "Maxsulot does not exist"},
                                status=status.HTTP_404_NOT_FOUND)

        try:
            maxsulot.delete()
        except Exception as e:
            return JsonResponse({"status": "Error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return JsonResponse({"status": "Success", "message": "Maxsulot deleted"}, status=status.HTTP_204_NO_CONTENT)
