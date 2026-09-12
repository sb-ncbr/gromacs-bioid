FROM nginxinc/nginx-unprivileged:1.27
COPY bat3_validation/ui /var/www/app
COPY deploy/nginx-validation-ui.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
