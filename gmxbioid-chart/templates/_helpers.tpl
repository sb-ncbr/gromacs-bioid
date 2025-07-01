{{- define "gmd.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Return a TLS secret name of the form:
  <sanitized-host>-<fullname>-tls
where:
  - sanitized-host = ingress.host lowercased, dots → hyphens
  - fullname        = include "gmd.fullname" .
*/}}
{{- define "gmd.TlsName" -}}
  {{- $host := .Values.ingress.host | lower | trunc 14 -}}
  {{- $sanitized := $host | replace "." "-" -}}
  {{- printf "%s-%s-tls" $sanitized (include "gmd.fullname" .) -}}
{{- end -}}