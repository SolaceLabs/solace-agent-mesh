interface DocResourceCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  link: string;
}

const DocResourceCard = ({
  icon,
  title,
  description,
  link,
}: DocResourceCardProps) => {
  return (
    <a
      href={link}
      target="_blank"
      rel="noopener noreferrer"
      className="flex p-4 bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors group items-center"
    >
      <div className="mr-4 flex-shrink-0 bg-solace-blue bg-opacity-10 p-3 rounded-lg text-solace-blue group-hover:bg-opacity-20">
        {icon}
      </div>
      <div>
        <h4 className="font-medium text-gray-800">{title}</h4>
        <p className="text-sm text-gray-600">{description}</p>
      </div>
    </a>
  );
};

export default DocResourceCard;
