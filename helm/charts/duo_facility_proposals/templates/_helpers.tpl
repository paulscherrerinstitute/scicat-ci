{{/*
Expand the name of the chart.
*/}}
{{- define "duo_facility_proposals.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "duo_facility_proposals.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "duo_facility_proposals.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "duo_facility_proposals.labels" -}}
helm.sh/chart: {{ include "duo_facility_proposals.chart" . }}
{{ include "duo_facility_proposals.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "duo_facility_proposals.selectorLabels" -}}
app.kubernetes.io/name: {{ include "duo_facility_proposals.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Selector labels filter
*/}}
{{- define "duo_facility_proposals.selectorLabelsFilter" -}}
{{ include "duo_facility_proposals.selectorLabels" . | splitList "\n" | join "," | replace ": " "=" | quote }}
{{- end }}

{{/*
Get facilities schedule from yaml file or default to Values.yaml
*/}}
{{- define "duo_facility_proposals.facilities_schedule" -}}
{{- if .Values.facilities_schedule }}
{{- .Values.facilities_schedule }}
{{- else }}
{{ .Values | toYaml }}
{{- end }}
{{- end }}


{{/*
Compose pod and cronjob name based on facility and year
*/}}
{{- define "duo_facility_proposals.resource_name" -}}
{{- $withFacility := printf "%s-%s" .fullname .name }}
{{- if .year }}
{{- printf "%s-%d" $withFacility (.year | int) }}
{{- else }}
{{- $withFacility }}
{{- end }}
{{- end }}

{{/*
Validate the secret, checking if base64 encoded
*/}}    
{{- define "validateSecret" -}}
{{ $secret := regexReplaceAllLiteral "\u0026#x3D;" (regexReplaceAllLiteral "\u0026#x2F;" . "/") "=" }}
{{- if (b64dec $secret | hasPrefix "illegal base64") -}}
{{ fail "Please b64 encode your secrets!" }}
{{- else }}
{{- $secret }}
{{- end }}
{{- end }}
