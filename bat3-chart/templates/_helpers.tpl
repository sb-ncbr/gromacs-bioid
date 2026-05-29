{{/*
Expand the name of the chart.
*/}}
{{- define "bat3.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "bat3.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a TLS secret name from the ingress host.
Sanitize: lowercase, dots to hyphens, truncate to 14 chars.
Format: {sanitized}-{fullname}-tls
*/}}
{{- define "bat3.TlsName" -}}
{{- $host := lower .Values.ingress.host }}
{{- $sanitized := $host | replace "." "-" | trunc 14 }}
{{- printf "%s-%s-tls" $sanitized (include "bat3.fullname" .) }}
{{- end }}
